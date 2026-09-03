## [2026-09-03] Ticket 034 : le vélo d'un persona dépend de l'ordre du fichier, et deux lois cohabitent

Constat consigné, sans changement de comportement (décision non prise). L'attribution du vélo
personnel et le choix VAE / vélo normal hachent la position du persona dans le fichier et une clé
d'adresse : entre le vivier pré-imputé et la cohorte v4 qui en est extraite, 201 personas sur
1 000 changent de vélo alors que la distribution globale et les douze contrôles ne bougent pas.
Et la loi apprise sur EMC² tourne à deux endroits — dans le fork eqasim, contre la décision du
24 août, et à l'étape 8 du notebook, qui réécrit 4,7 % du vivier. Le ticket propose une clé
stable (identifiant de personne et de ménage, sel `personal_bike_v2`) au prochain scellement et
le retrait de la loi du fork ; les deux pages d'architecture disent désormais ce que le code fait.

---

## [2026-09-03] Une page raconte comment la population du jeu de test est fabriquée

`docs/paper/population/fabrication_population_v4_2026-09-03.html` suit le fichier de bout en bout :
ce qu'eqasim consomme (recensement, ENTD 2008, FILOSOFI, BD TOPO, BAN) et ce que le fork y règle
(six départements, 453 communes, appariement national, borne d'âge 17, jours de classe, pondération
des communes sans IRIS), la chaîne des stages, les étapes du notebook (journée, desserte TC, zone
fine, pré-imputation, sélection par ménages entiers, routage sur le graphe du polygone, export,
traits, audit), puis le contrôle, l'audit de périmètre et le scellement — avec, à chaque étage, les
résultats mesurés sur la v4 et un tableau récapitulatif. Elle complète la synthèse de représentativité,
qui juge ; celle-ci explique. Elle se régénère (`make synthese-generation-population`) depuis les
mêmes fichiers que la synthèse, plus la méta du graphe OSMnx et les mesures du graphe ; les seuls
chiffres sans fichier structuré (journal de génération eqasim) sont marqués d'une croix et sourcés.

---

## [2026-09-03] La synthèse de représentativité porte le verdict vélo et le bon compte des déplacements

La page « La population scellée v4 est-elle représentative de l'enquête ? » lit désormais le contrôle
de l'équipement vélo dans deux rapports structurés — celui de la cohorte scellée et celui du vivier —
au lieu de l'ignorer : le nombre de contrôles ok, la pente du taux de porteurs par taille de ménage
et son verdict (« non concluant » sur 1 000 agents, « croissante » sur le vivier) figurent dans le
niveau 3 du verdict et dans le tableau de ce que la sélection ne referme pas. Le contrôle vélo gagne
pour cela l'option `--rapport-json`, qui écrit ce que la console affichait (contrôles, marges,
pente, verdicts, code de sortie), et la cible `make synthese-representativite` prend `VELO=` et
`VELO_VIVIER=`. Le sous-titre du graphique de mobilité disait encore « activités − 1 » : il dit la
convention en vigueur, n déplacements pour n activités, retour au domicile compris.

**Avant :** la synthèse v4 ne disait rien du vélo, et son graphique de mobilité portait une légende
périmée.
**Après :** cohorte v4 — 12 contrôles ok, pente non concluante (27,3 / 44,4 / 63,4 / 55,5 % sur
218 / 148 / 69 / 55 foyers) ; vivier — 14 contrôles ok, pente croissante (32,8 / 49,1 / 55,0 /
60,9 % sur 2 350 / 1 657 / 744 / 532 foyers). Chiffres lus dans les rapports JSON, jamais saisis.

---

## [2026-09-03] La pente de l'équipement vélo se juge sur le vivier, pas sur mille agents

Le contrôle de l'imputation du vélo personnel vérifie que le taux de porteurs croît avec la taille
du ménage. Il jugeait ce critère dès 30 foyers par taille et exigeait une croissance stricte : sur
la cohorte scellée v4, 63,4 % chez les ménages de 3 personnes contre 55,5 % chez ceux de 4, sur 69
et 55 foyers, le déclaraient « démenti » alors que l'intervalle d'incertitude fait ± 12-13 points.
Le critère est désormais jugé à partir de 100 foyers par taille, une inversion n'est un échec que
si elle dépasse l'incertitude combinée des deux cellules, et sur une cohorte de 1 000 agents il
s'affiche « non concluant » sans peser sur le verdict : c'est sur le vivier, où chaque taille
compte des centaines de foyers, que la pente est opposable.

**Avant :** `--check` sortait en échec (code 2) sur la cohorte v4 pour ce seul critère ; le vivier
n'était pas regardé.
**Après :** cohorte v4 : 12 contrôles ok, pente « non concluante », code 0 ; vivier v4 (11 329
personnes) : 14 ok, pente croissante 32,8 / 49,1 / 55,0 / 60,9 %. Les tolérances par taille et les
autres cibles du ticket 015 ne changent pas.

---

## [2026-09-03] Le compte des déplacements inclut le retour au domicile

Le contrôle de population comptait `n − 1` déplacements pour `n` activités, comme si la journée
était une chaîne ouverte. Or la chaîne est cyclique : l'étape 2 du notebook fusionne le domicile du
soir et celui du matin en une seule activité, et le routage des horaires calcule bien `n` trajets,
le dernier ramenant au domicile. Une journée domicile → travail → domicile, deux activités, faisait
un seul déplacement au lieu de deux. Chaque persona mobile était sous-compté d'un déplacement, et
l'« écart de mobilité » déclaré à publier depuis la v2 était pour l'essentiel cet artefact.

**Avant :** v4 : 2,44 déplacements par persona, 2,73 par persona mobile ; v3 : 2,58 / 2,88 —
contre 3,53 / 3,95 dans l'enquête, écart « à publier ».
**Après :** v4 : 3,33 / 3,73 ; v3 : 3,47 / 3,88. L'écart restant (0,2 par persona) passe sous le
seuil de 0,3 : la mobilité n'est plus un écart à publier, elle se lit dans la section ménages et
mobilité du rapport. Le sceau v4 est rescellé avec le rapport corrigé, même population, même
empreinte.

---

## [2026-09-03] Le recoupement du protocole compare enfin le tableau corrigé

Le rapport de contrôle d'une population recoupe chaque chiffre du tableau de conformité
démographique du protocole (§ 2.1) avec sa référence recalculée. Il comparait encore les neuf
valeurs de la v1.3 du protocole, retirées le matin même parce qu'elles n'avaient pas de source
(51,8 / 19,4 / 62,1 / 18,5 / 22,3 / 46,1 / 31,6 / 84,2), et produisait des lignes « écart à
consigner » sur des chiffres qui n'existent plus. Il recoupe désormais les treize lignes du
tableau v1.5 — genre, six classes d'âge publiées, motorisation en base ménage, permis, personnes
sans déplacement — contre les cibles gelées `cm1`, les six classes de la p. 11 et la base ménage
de la p. 21.

**Avant :** sur la population scellée v4, 9 lignes de recoupement dont 8 « ÉCART — à consigner ».
**Après :** 13 lignes, toutes concordantes ; un manuscrit qui citerait une autre cible que celle du
dépôt serait signalé, ce qui est le rôle du recoupement.

---

## [2026-09-03] Population scellée v4 : le périmètre des 453 communes, six départements, appariement national

Le jeu de test de l'article est rescellé — `data/population/population_1000_AAMAS_v4/`, sha256
`9f05c655c3ad2cf4…` — sur le **périmètre exact de l'enquête EMC² 2023** : 453 communes de six
départements, délimitées par le polygone des communes. Ce que porte ce sceau et que les
précédents n'avaient pas :

- **Le périmètre entier.** BD TOPO 2025-03-15 et BAN des six départements dans le fork ; six
  départements représentés dans la cohorte (31 : 939, 32 : 9, 81 : 30, 82 : 19, 09 : 2, 11 : 1),
  53 des 154 habitants de 3ᵉ couronne hors Haute-Garonne comme les 35 % de l'enquête. Au passage,
  un biais du cadre par liste de communes est corrigé : les personnes du recensement à commune
  « undefined » (communes sans IRIS) étaient toutes gardées puis versées dans les communes du cadre
  — 17 986 personnes pour 10 000 demandées et 42,5 % en 3ᵉ couronne au premier essai ; elles sont
  désormais pondérées par la part du cadre dans la population sans IRIS du département.
- **Des chaînes d'activités appariées sur l'ENTD nationale**, un jour de classe, avec une borne
  d'âge à 17 ans : 88,5 % des écoliers mobiles ont une activité d'études (v3 : 54 %) ; les 15-17 ans
  passent de 80 à 92 % dans le vivier.
- **Des horaires recalés sur le graphe du polygone**, avec la congestion par zone d'arête et le
  repli « même nœud » à la vitesse du mode : 3 291 paires, 3 274 routées, 17 `None`, 582 s à
  3 workers (177 ms par route, sans swap une fois les conteneurs non nécessaires arrêtés).
- **Une hypothèse déclarée** : une activité hors du polygone sortirait de la chaîne (0 ce jour),
  et le MANIFEST le dit.

**Avant (v3) :** 346 communes haut-garonnaises, 308 donneurs de chaînes, 54 % des écoliers à l'école,
13 marges conformes, 2,88 déplacements par agent mobile.
**Après (v4) :** 453 communes, ENTD nationale, **88,5 %** des écoliers à l'école, **12 marges
conformes et 1 à publier** (motorisation en base ménage : sans voiture 22,8 % contre 19,2 %),
immobiles 10,6 %, 2,73 déplacements par agent mobile (enquête 3,95) ; audit A2 / A4 / A9 conformes.
À publier aussi : la pente de l'équipement vélo par taille de ménage n'est pas monotone entre les
tailles 3 et 4 (chaque taille dans sa tolérance, 55-69 foyers).

Sauvegarde `data/population/sauvegardes/population_1000_AAMAS_v4_2026-09-03.tar.gz` (sceau + vivier),
`config.yaml` repointé, synthèse HTML v3 dans `docs/paper/population/`. ⚠ Le runtime filtre encore
sur le rectangle du graphe de 30 km : le sceau ne se charge entier qu'après le portage de la
partie 2 du ticket 031. Deux robustesses au passage : le notebook ne sollicite plus eqasim quand
ses viviers bruts sont en cache, et le lien `experiments/current` se repointe atomiquement (trois
workers de routage spawnés dans la même seconde faisaient tomber le pool).

---

## [2026-09-03] La congestion routière s'applique par zone d'arête : ville, agglomération, rien dehors

Le facteur de congestion TomTom ne s'applique plus à un trajet entier mais **arête par arête**,
selon la zone du nœud d'origine de l'arête : profil « ville » dans la commune de Toulouse, profil
« agglomération » dans les couronnes Toulouse + 1ʳᵉ + 2ᵉ de l'enquête, **facteur 1,0 au-delà**
(3ᵉ couronne). Les zones sont posées une fois sur les nœuds du graphe — à la construction du
graphe du polygone des 453 communes, ou paresseusement au premier chargement du graphe historique
de 30 km — puis mises en cache dans le pickle ; un nœud sans zone est une erreur explicite, pas un
facteur deviné. Décision de l'auteur du dépôt (ticket 031, question 4), livrée avant le routage
des plannings de la v4 pour que le sceau porte des horaires recalés sur ces durées.

**Avant :** un trajet Cazères → Muret un lundi à 8 h était multiplié par 1,84 (profil
« agglomération ») sur toute sa longueur, comme un trajet Colomiers → Blagnac ; un trajet
touchant Toulouse par un bout était à 2,04 partout.
**Après :** Cazères → Muret n'est congestionné que sur ses kilomètres agglomérés (facteur global
≈ 1,1 à 1,3 selon la part), un village → village de 3ᵉ couronne roule à vitesse libre, et un
trajet 3ᵉ couronne → centre de Toulouse cumule 1,0 sur la campagne, 1,84 dans l'agglomération et
2,04 dans la ville.

Sur le graphe du polygone des 453 communes (zones posées le 2026-09-03, 18 s) : marche 176 340
nœuds — 32 342 en ville, 102 858 en agglomération, 41 140 dehors ; vélo 23 202 / 89 453 / 39 178 ;
voiture 8 878 / 38 447 / 17 825 (`graphs_444ca7e6a515.meta.json`).

---

## [2026-09-03] Les trajets trop courts pour le graphe durent à la vitesse de leur mode, et une activité hors périmètre sort de la chaîne

**Repli « même nœud » du routage OSMnx.** Quand l'origine et la destination d'un trajet se
rabattent sur le même nœud du graphe, il n'y a rien à router. Le repli calculait la durée à
70 km/h quel que soit le mode : écrit pour des points hors du graphe de 30 km (trajets lointains
de 3ᵉ couronne), il servait aussi aux vrais trajets courts. Avec le graphe du polygone des
453 communes, il ne reste que ces derniers — la durée vient désormais de la vitesse de repli du
mode (marche 5, vélo 14, voiture 30 km/h) sur la distance à vol d'oiseau × 1,3 de détour,
minimum 1 s ; la distance rendue est celle du détour. Ce repli sert aussi au recalage des
horaires du notebook (étape 4+5).

**Avant :** 200 m à pied = 10 s, affiché « 0 minute » ; 200 m à vélo ou en voiture, 10 s aussi.
**Après :** 200 m à pied ≈ 3 min (187 s), à vélo 67 s, en voiture 31 s ; 0 m = 1 s.

**Activités hors du polygone des 453 communes** (hypothèse assumée du ticket 031) : une activité
située hors du périmètre d'enquête est supprimée de la chaîne de la personne à l'étape 2 du
notebook, avant le recalage des horaires — jamais le domicile —, comptée à la racine de
l'enregistrement, alarmée si le compte dépasse 0, reprise dans le journal de sélection et le
MANIFEST du sceau (« activités hors périmètre : n supprimées », ou « non contrôlé » pour une
population produite avant le garde-fou). Mesuré : 0 sur les viviers du jour.

**Critère 3 du ticket 031 reformulé** : ce qui mesure un défaut de graphe, ce sont les paires
« même nœud » distantes de plus de 500 m à vol d'oiseau (≤ 0,5 % attendu par couronne) ; les
paires plus courtes sont de vrais trajets courts. Le script de mesure les distingue.

---

## [2026-09-03] Car scolaire synthétique pour les mineurs périurbains (ticket 030)

Les personas de 5 à 17 ans dont le domicile est hors du ressort Tisséo reçoivent désormais, sur
leurs trajets vers ou depuis l'école, une option **« car scolaire liO (gratuit) »** — le premier
mode collectif des 2ᵉ et 3ᵉ couronnes, absent de tous les GTFS. L'option est synthétique (aucun
appel OTP/OSMnx) : horaire calé sur l'activité scolaire (± 30 min), durée calibrée sur l'EMC²
(médiane ≈ 30 min), coût nul. Elle est **comptée en transport collectif** partout — journal
`moves.csv`, cibles EMC², oracle LightGBM — et n'apparaît jamais pour un adulte, ni pour un trajet
sans lien avec l'école, ni pour un domicile desservi par Tisséo.

**Avant :** un écolier de 3ᵉ couronne sans arrêt Tisséo à proximité n'avait aucune option de
transport collectif ; sa part TC était nulle par construction, et la 3ᵉ couronne simulée était
structurellement « tout voiture ».
**Après :** il se voit proposer un car scolaire gratuit, arrivant 30 min avant le début des cours,
et le choix revient au modèle comme pour tout autre mode.

Éligibilité : **âge seul** (5-17) + zone hors ressort Tisséo, sans critère de sectorisation ni de
distance minimale (les circuits réels ne sont pas demandés à la Région). Rendu GAMA hors périmètre :
l'agent se déplace correctement (interpolation point-à-point via le marqueur `__DIRECT_CAR__`) mais
s'affiche en rouge (couleur voiture), sans effet en run headless. Caches de décision et sémantique
vidés à la livraison (le jeu d'options change).

---

## [2026-09-03] Plan expérimental AAMAS : incertitude quantifiée, seeds explicites, symétrie presse et bras de sensibilité λ

Le plan expérimental (`docs/paper/experience_plan/`) devient auto-porteur sur les points qui
faisaient réagir en revue. L'unité d'évaluation est clarifiée : la cohorte scellée est de
**1 000 personnes** (894 mobiles) produisant **≈ 2 579 trajets** (2,58/pers, mesuré), et non
« 1 000 trajets ». Chaque métrique se publie désormais avec son incertitude, chaque expérience
porte un `seed`, les trois événements de presse ont la même batterie de contrôles, et le critère
de réfutation de l'hystérésis est réellement exécutable.

**Avant :** `trip_count: 1000` ambigu (personnes ou trajets ?) ; métriques en point-estimate nu,
sans IC ni test ; seed présent seulement sur les LLM ; conditions paraphrase/placebo/oracle sur le
seul événement Minotaure ; un unique λ, donc impossible de tester « diviser λ par trois déplace la
courbe » ; nom de modèle « Gemini 2.5 » incohérent avec le reste.

**Après :** `person_count: 1000` + `trip_count: 2579` (dérivé, recalculé au gel) ; bloc
`scoring.uncertainty` (cluster bootstrap par agent → IC95 ; McNemar apparié pour Phases 4-5 ;
TOST ±1 pt pour le calage macro) ; `seed: 42` sur tous les moteurs (heuristiques, tabulaires,
LLM) ; Canicule et Rocade complétés aux **5 conditions** (Canicule = « pire cas » de suivi de
consigne) ; nouveau bras `exp_04d` (λ=0,13 = λ÷3) ; nommage `gemini-3.1-flash-lite-preview`
partout. Plan porté à **29 expériences**.

---

## [2026-09-03] Le périmètre des 453 communes entre dans la chaîne de population : six départements, graphe du polygone, règle v4

Le périmètre d'étude est désormais celui de l'enquête EMC² 2023 — **453 communes sur six
départements, délimitées par le polygone des communes** — et la chaîne de population le porte de
bout en bout (ticket 031, partie 1). Ce qui change pour qui génère, sélectionne ou contrôle une
population :

- **eqasim tire dans les 453 communes.** `config_toulouse.yml` demande les six départements et la
  liste des communes ; le stage des codes spatiaux journalise le cadre par département
  (346 / 38 / 27 / 22 / 10 / 10) et refuse une commune inconnue du référentiel. Le service Docker
  vérifie **avant** de générer que chaque département demandé a sa BD TOPO et sa BAN : un
  département sans données ne se « saute » pas. Tant que les données des cinq départements hors
  Haute-Garonne ne sont pas là (accord de l'auteur requis), la chaîne tourne en **répétition**
  sur les 346 communes du 31, et une population tirée sur ce cadre ne se scelle pas en v4.
- **`household.commune_id` et `iris_id` sont renseignés pour tous les ménages** (36 % valaient
  « undefined ») : le runtime pourra filtrer par commune du domicile (partie 2).
- **Le service Docker applique enfin les réglages d'appariement de `config_toulouse.yml`.**
  Constaté ce jour : sa configuration synpp ne portait ni `filter_hts: false`, ni les attributs
  d'appariement, ni le seuil — synpp retombait sur **308 donneurs ENTD** résidents de
  Haute-Garonne pour 12 000 personnes, classe d'âge abandonnée par la dégradation. Les chaînes
  d'activités de toutes les populations générées par le service, **v3 comprise**, viennent de ce
  vivier réduit : c'est une part de l'écart de mobilité « à publier » et de la moitié des écoliers
  sans école. Le service part maintenant du fichier de configuration (monté) et refuse de générer
  sans lui.
- **Les journées donneuses sont des jours de classe, sans effet de bord.** La première version du
  filtre (matin) laissait les donneurs en vacances dans le vivier comme immobiles : 40,6 %
  d'immobiles générés. Ils en sortent désormais.
- **Le routage des plannings (étapes 4+5 du notebook) se fait sur les graphes du polygone des
  453 communes** — `make osmnx-perimeter-graph` les construit sans téléchargement depuis les pbf
  OSM du fork, avec les filtres réseau d'OSMnx et les vitesses de la production, sous une clé de
  cache distincte du disque de 30 km (qui reste celui du runtime : partie 2).
- **La sélection passe à la règle `aamas_seal_v4`** : six classes d'âge du rapport dans la
  descente, journal du périmètre et des départements de résidence des retenus dans le sceau.
  Le contrôle gagne la ligne **« scolaires (6-17 ans) avec activité d'études »** face à l'EMC²
  (90 à 95 %, seuil 88 %).

**Avant :** vivier v3 tiré sur la Haute-Garonne avec 308 donneurs de chaînes ; 57,5 % des 6-17 ans
mobiles avec une activité d'études ; 2,58 déplacements par persona ; trajets de 3ᵉ couronne
rabattus sur un même nœud du graphe de 30 km (98 des 154 agents dehors) ; `household.commune_id`
« undefined » pour 36 % des personnes.
**Après (vivier de répétition Haute-Garonne, 11 922 personnes, 6 min) :** 0 domicile hors des
453 communes, `household.commune_id` renseigné pour tous, **89,0 %** des 6-17 ans mobiles avec une
activité d'études (6-10 ans 91,9 %, 15-17 ans 80,4 %), 2,93 déplacements par persona et 3,63 par
mobile (enquête 3,53 / 3,95) ; graphes du polygone : marche 176 k nœuds, vélo 152 k, voiture 65 k
(+30 % de voirie pour une surface × 1,9), pickle 223 Mo, 1,6 Go par worker de routage. La chaîne
complète en répétition (sélection v4 de 1 000 personas en 505 ménages entiers, routage sur le
polygone, export, traits, audit) donne un contrôle à **13 marges conformes**, immobiles 10,6 %,
**89,3 %** des scolaires mobiles avec une activité d'études, audit A2 / A4 / A9 conformes — sans
sceau, parce que le cadre est encore la Haute-Garonne.

Ce qui reste : les données BD TOPO et BAN des départements 32, 81, 82, 09 et 11 (porte
d'approbation ; l'IGN ne sert plus l'édition 2024-09-15 de la Haute-Garonne, seule la 2025-03-15
est disponible) ; le sceau v4 ; le portage du runtime, d'OTP et de GAMA sur le polygone (partie 2
du ticket, analysée, non spécifiée).

---

## [2026-09-03] Les chaînes d'activités des agents viennent de jours de classe

Le générateur de population prend ses chaînes d'activités dans l'ENTD 2008, qui couvre l'année
entière ; l'EMC² 2023, référence du jeu de test, s'enquête hors vacances scolaires. Le fork
eqasim ne garde plus comme journées donneuses que les jours de classe : hors vacances scolaires
pour tout le monde, et hors mercredi pour les moins de 11 ans (les écoliers de 2008 n'avaient
pas classe ce jour). Réglages `hts_school_days_only` et `hts_exclude_wednesday_under_age` ;
le stage imprime la part des scolaires mobiles avec un trajet vers l'école et alarme sous 85 %.

**Avant :** 50 à 54 % des 6-17 ans du vivier avaient une activité d'études un jour de semaine
(EMC² : 90 à 95 %) ; dans la population scellée v3, 69 des 151 mineurs mobiles passaient un
lundi sans école.
**Après :** sur les journées donneuses, 72,0 % → 90,8 % des scolaires mobiles ont un trajet vers
l'école ; 15 687 → 12 392 donneurs (−21 %), la plus petite classe d'âge en garde 858 pour un
seuil de 5. Le vivier et le sceau v4 restent à régénérer (ticket 031).

---

## [2026-09-03] La population scellée passe à 13 marges conformes : ménages entiers, marges multiples, immobiles rendus

La règle de sélection v3 (ticket 029) remplace la v2 pour le jeu de test de l'article. Trois
changements, chacun pour un écart mesuré sur la population scellée de la veille.

**Sélection par ménage.** L'unité n'est plus la personne mais le ménage entier (`household.id`) :
la cohorte de 1 000 vient de **514 ménages complets** — tous leurs membres de 5 ans et + sont
présents — au lieu de 865 ménages dont 308 complets. Ce que la négociation intra-ménage et la
chaîne de véhicules attendaient.

**Descente sur marges multiples.** Après l'allocation aux 12 cellules couronne × motorisation,
des échanges de ménages de même taille et même cellule ramènent **huit marges** sur leurs cibles :
occupation, âge quinquennal, genre, taille de ménage, permis, abonnement TC, logement, part
d'immobiles. Sept cibles que le rapport ne publie pas à ce pas sont recalculées sur les
microdonnées et gelées (`cm1`) ; genre et permis deviennent mesurables. Le vivier est
pré-imputé avant la sélection pour que logement, permis et abonnement soient des marges.

**Les six classes d'âge du rapport entrent dans la descente.** Tenir les quinze classes
quinquennales ne tenait pas la part des 5-17 ans (+1,2 pt sur la v3 : la classe 15-19 chevauche
la frontière 17/18). Le référentiel de l'article étant le rapport AUAT, ses six classes sont
désormais des marges de la sélection ; effet au prochain scellement.

**Les immobiles reviennent.** L'export eqasim écartait toute personne sans activité hors
domicile ; l'enquête en compte 10,6 %. Ils restent (journée « domicile », drapeau `immobile`),
la sélection les ramène exactement à **10,6 %**, et deux gardes de la chaîne qui plantaient sur
une journée à une activité sont corrigées.

**Avant :** v2 — 6 marges conformes sur 6 contrôlées, mais 75 ans et + à 9,8 % (7,1 attendus),
0 % d'immobiles, ménages fragmentés (54,6 % de membres absents).
**Après :** v3 — **13 marges conformes, 0 à corriger, 0 à publier, 0 non mesurable** ; 2,5 % de
membres absents ; vivier de 11 922 (10 000 demandés, 209 s d'eqasim) dont la sélection ne garde
que 8,4 %. Le seul écart restant à publier est la mobilité des agents mobiles (2,88 déplacements
contre 3,95) : celui des chaînes d'activités ENTD 2008, prochain levier.

Scellé `data/population/population_1000_AAMAS_v3/` (sha256 `8d8bfa3645fa77fb…`), sauvegardé avec
son vivier, runtime repointé ; le sceau v2 reste intact. Le run GAMA avec des agents immobiles
est à vérifier au premier lancement.

---

## [2026-09-02] La population du jeu de test se contrôle contre l'enquête, puis se scelle

Première étape des travaux pour l'article AAMAS (§ 3.1 du gabarit, jalon 0 du protocole) :
une population synthétique se **contrôle** marge par marge contre la population enquêtée par
l'EMC² 2023, et, si elle passe, se **scelle** dans un dossier immuable avec son empreinte, la
règle qui l'a produite et le rapport qui l'a jugée. Trois cibles `make` : `control-population`,
`select-population`, `seal-population` (et `reference-marges` pour voir d'où vient chaque cible).

**Ce que le contrôle rend.** Pour chaque modalité — classes d'âge, occupation, motorisation sur
base personne *et* sur base ménage, couronne de résidence, et le **croisement** couronne ×
motorisation (là où une synthèse par marges échoue sans qu'aucune marge ne bouge) — la part
observée, son IC95, la cible et sa page dans le rapport, l'écart, le verdict TOST à ± 1 pt ;
par marge, le χ² demandé par le gabarit avec son V de Cramér, EMD ou JSD aux définitions
exactes du moteur de score. Une marge sans cible publiée (sexe, permis : absents du rapport)
sort `non mesurable` avec sa raison, jamais 0. Le rapport termine par une **synthèse des
écarts** — amplitude, nature, refermable au scellement ou non — et par le **journal de
recoupement** du tableau § 2.1 du protocole : ses neuf lignes s'écartent de la référence
(« moins de 18 ans » 19,4 % publié contre 16,0 % dans l'enquête, « 18-64 » 62,1 % contre
68,0 %, ménages sans voiture 22,3 % contre 19,0 %), à consigner en Annexe F.

**Deux bases, désormais distinguées.** Le rapport publie la motorisation par ménage (19 / 45 /
35 %) ; une population synthétique est un échantillon de personnes, où « deux voitures et + »
pèse **48,7 %**. La cible jointe sur base personne, que personne ne publie, est recalculée sur
les microdonnées et **gelée** (`scripts/AAMAS/cible_jointe_couronne_motorisation.yaml`, avec
provenance) : le contrôle tourne sans les microdonnées d'accès restreint.

**Avant :** « 1 000 agents » en contenait 1 021 (eqasim tire 15 % de plus et renomme le
fichier), le runtime en ré-échantillonnait 930 au hasard, et la conformité démographique du
protocole reposait sur un tableau non recoupé.
**Après :** `select` tire 1 000 personas pile par allocation proportionnelle aux 12 cellules
couronne × motorisation de l'enquête (ordre `sha256`, déterministe), exclut les 45 domiciles
hors périmètre, journalise tout déficit, puis **équilibre l'occupation** par échanges à
l'intérieur des cellules — le générateur produit 7,4 % d'actifs à temps partiel pour 5 % dans
l'enquête, et 50 échanges suffisent à remettre les sept postes sur la cible sans déplacer une
cellule ; `seal` **refuse** de sceller s'il reste un « à corriger ». Sur la population de référence actuelle, le contrôle rend 4 « à corriger »
(couronne −5,9 pt sur la 3ᵉ couronne, joint, âge, occupation), 2 conformes (motorisation, deux
bases), 2 non mesurables.

**Chaîne de génération.** Le notebook gagne une étape **3ter** — la sélection, placée *avant*
les étapes de routage : on génère un vivier (`POPULATION_SIZES = [5000]`, seuil calculé pour
remplir les 12 cellules dans 99,2 % des tirages) et seuls les 1 000 retenus passent au
scheduling et au réchauffage OSMnx. L'export eqasim pose à la racine de chaque enregistrement
`household` (id, iris, commune), `provenance` (donneurs RP et ENTD) et `validation.commute_mode`
— le mode de navette déclaré, vérité terrain par individu qui **ne doit pas atteindre le
prompt**. Ces champs vivent hors de `traits_json` : ils n'entrent ni dans le narratif ni dans
la clé du cache.

**Le runtime prend le sceau entier.** Nouveau réglage `data.population_file` : un fichier de
population désigné explicitement remplace la recherche par taille et tout appel à eqasim. Il
est pris tel quel — s'il ne compte pas exactement `population_size` agents après le filtre bbox,
le chargement **refuse** au lieu de ré-échantillonner au hasard comme avant : un sceau ne se
rogne pas en silence.

**Population scellée le 2026-09-02.** `data/population/population_1000_AAMAS/` — 1 000 personas
(sha256 `f67b0777…`), tirés dans un vivier de 5 063 : **six marges conformes** (classes d'âge,
occupation à l'unité, motorisation sur les deux bases, couronne, couronne × motorisation), genre
et permis non mesurables faute de cible publiée ; audit de périmètre A2, A4, A9 conformes. Le
run lit ce fichier via `data.population_file`. Limite nouvelle, mesurable grâce à `household.id` :
la sélection par personne ne retient que 308 ménages complets sur 865 — sans effet sur le choix
modal individuel, à déclarer pour tout ce qui dépend des co-résidents.

**Le réchauffage OSMnx devient optionnel.** L'étape 6 du notebook (≈ 78 000 routes pour 1 000
personas) ne touche pas à la population ; elle pré-calcule le cache d'itinéraires. `SKIP_WARMUP`
la saute — le runtime calcule les itinéraires manquants à la demande — et `MAX_WORKERS` devient
un paramètre : à 12 workers chaque copie des graphes fait swapper la machine (23 Go mesurés, workers
à 50 % de CPU, des heures de calcul) ; à 6 elle tient en RAM.

---

## [2026-09-02] Le temps terminal et la résidence parlent enfin du même découpage

Le temps d'accès au véhicule et de stationnement était facturé selon des **anneaux de
distance** autour du Capitole (8 / 20 / 40 km), alors que la couronne de résidence des
personas — et toutes les cibles de l'enquête — suivent la **liste de communes** de l'EMC².
Un même trajet pouvait donc être « Toulouse » pour le stationnement et 1ʳᵉ couronne pour le
journal. Les lois de temps terminal sont re-stratifiées sur la table de l'enquête (`tt4`,
ticket 028) et les points d'origine et de destination sont classés par appartenance aux
couronnes.

**Avant :** Blagnac, Balma, Ramonville — à 5 ou 6 km du Capitole — payaient le stationnement
de centre-ville ; 25,6 % des trajets d'enquête restaient hors strates et la loi de la 3ᵉ
couronne reposait sur 409 trajets ; un point à 100 km recevait la loi de la 3ᵉ couronne en
silence.
**Après :** ces communes paient la loi de la 1ʳᵉ couronne ; 3,9 % de trajets hors strates et
3 370 trajets pour la 3ᵉ couronne ; un point hors des 453 communes reçoit la loi d'ensemble,
est compté (`terminal_time_out_of_perimeter_total`) et déclenche une alarme `[ALARME]` une
fois. Les moyennes d'ensemble ne bougent pas (0,24 / 0,32 min) : même mesure, autre découpage.

⚠ Le passage `tt3 → tt4` **invalide le cache de plans OTP et le cache de décisions LLM** : le
prochain run repart à froid sur ces deux caches (le cache de routage OSMnx, `r1`, est
conservé). C'est voulu — une population propre pour l'ensemble des tests AAMAS.

**Audit de périmètre.** L'axe A2 ne remesure plus l'écart historique de 24,4 % : il vérifie que
le trait `residence_zone`, la géométrie des couronnes et la ressource de temps terminal sont
sur le même découpage, et passe `conforme` sur la population de référence (1 021/1 021). A9
perd sa colonne « publié par le classement métrique », qui n'existe plus. La fonction
métrique ne survit que comme témoin des scripts de mesure archivés, et un test garantit
qu'aucun module de production ne l'importe.

**Calendrier du run (axe A6).** Le contrôleur journalise le jour de semaine du départ de
simulation — `[ALARME]` s'il tombe un week-end, avertissement si ce n'est pas un lundi — et
alarme une fois quand un départ de week-end est reporté au lundi : l'enquête ne compte aucun
week-end, et les reports s'empilent sur le lundi.

---

## [2026-09-02] Le support de séminaire prend la forme d'un article

Le support passe de 41 à **31 planches** et adopte la forme d'un article : planche *Abstract* en texte
suivi, sections numérotées de 1 à 11, figures et tables légendées et référencées (« Figure 3 — … »,
« cf. § 3.3 »), section *Limites*, planche *Références*. Le titre est celui du papier :
*Évaluation empirique, limites et perspectives hybrides des agents LLM en simulation de mobilité urbaine*.

**Ce qui change dans la lecture.** Trois dispositifs de la première version disparaissent : la phrase de
thèse colorée sous chaque titre, les titres-aphorismes, et les encadrés qui expliquaient pourquoi une
précaution de méthode avait été prise. Les titres deviennent des intitulés de section — « Mesure de la
proximité aux enquêtes de terrain » plutôt que « Définir la mesure avant de mesurer ». Les remarques de
méthode passent en **notes de planche**, masquées en projection (touche `n`) et visibles en mode document
et à l'impression.

**Toute planche sans mesure le dit en grand.** Le statut « à produire » était une pastille de bas de page ;
il devient un **bandeau pleine largeur** en tête de planche, « Hypothèse — à confirmer par expérience »,
avec la raison à droite et une trame sur la figure concernée. Six planches le portent : modèles évalués,
variabilité inter-graines, registre de mémoire, dispositif sur cinq jours, plan à cinq conditions, cascade
hybride.

**Aucun résultat envisagé n'est plus tracé comme un résultat.** La courbe de ré-adoption sur cinq jours et
l'exemple de mémoire chiffré sont retirés : le protocole temporel décrit désormais son dispositif — trois
bras, cinq jours, fenêtre de mesure, grandeurs mesurées, critères de réfutation — sans aucune valeur de
sortie.

**Corrections de fond.** « Palier 3 : supervision » devient une **comparaison** aux modèles statistiques
estimés sur l'enquête : les deux familles ne se rangent pas sur le même axe d'ablation. La planche
d'importances de gain ne s'annonce plus comme une analyse SHAP — ce sont des parts de gain d'un modèle à
gradient boosté, et les deux quantités ne se substituent pas. Le choix de la taille de population devient
une planche à part entière, arbitrée entre coût d'inférence et peuplement des strates. Les références
triviales portent leurs scores. Trois planches sont supprimées : les deux erreurs L1, le plan en six
étapes, et la sensibilité du score à la définition de la distance.

**Avant :** un support qui argumentait, annonçait ses conclusions en sous-titre et signalait discrètement
qu'une mesure manquait.
**Après :** un support qui expose, numérote et légende, et qui affiche en tête de planche quand rien n'a
encore été mesuré.

Le lien de consultation est inchangé. Le fichier perd son numéro de version dans son nom
(`SLIDES_SEMINAIRE_2026.html`, version portée dans l'en-tête) et la version `v1.0` est figée dans `archive/`.

---

## [2026-09-02] Un support de séminaire, et onze chiffres du manuscrit remis d'aplomb

Le dossier `docs/paper/` gagne un **support de séminaire de 41 slides** (40–45 min) qui présente
l'article selon la démarche 0 → 1 → 2 → 3a → 3b → perspectives, avec un mode diaporama (flèches,
`d` pour basculer) et un mode document pour la relecture et l'impression. Chaque slide porte son
**statut de mesure** : mesuré et tracé dans le dépôt, partiel, ou à produire — on voit d'un coup d'œil
ce qui est déjà démontrable et ce qui reste à faire.

Il a été écrit en recoupant chaque chiffre citable avec sa source dans le dépôt plutôt qu'avec le
manuscrit. Ce recoupement a fait apparaître **onze écarts**, tous corrigés dans le manuscrit (`v1.4`),
le protocole (`v1.3`) et le plan (`v1.4`), et consignés dans un nouveau **journal des corrections**
(Annexe F du manuscrit). Les trois qui changent une conclusion :

- **La comparaison L1 opposait deux mesures différentes.** Les 2,68 pt attribués à l'oracle sont une
  erreur sur la *masse de probabilité* ; les 29,81 pt du LLM sont une erreur sur des *décisions dures*.
  À règle égale — argmax contre argmax — l'écart est de 7,30 contre 29,81, soit un facteur 4 et non 11.
- **La parité informationnelle portait sur 15 variables.** Le contrat servi en compte 21.
- **« 10 000 fois plus rapide »** devient ≈ 2 700 ×, d'après le tableau comparatif du manuscrit lui-même.

Les huit autres portent sur le statut de ce qui est affirmé : le jalon 0 est requalifié en **contrôle de
cohérence** (ces marges sont calées par construction, et un χ² non significatif ne prouve rien), la
dissymétrie d'exposition aux données est déclarée (l'oracle a vu 31 279 trajets, l'agent zéro), et
l'effectif devient obligatoire à côté de tout composite — 5,02 points de loss s'expliquent par le seul
passage de 881 à 81 personnes, à décisions inchangées.

**L'étape 3 devient réfutable.** Le protocole d'évaluation sur la presse locale passe de trois à
**cinq conditions** : s'ajoutent une paraphrase sans indice modal (l'article contient souvent la réponse —
« métros renforcés » —, sans quoi on mesure du suivi de consigne), un article placebo pris parmi les
sept que la grille d'expertise avait éliminés, et un **oracle recevant l'événement encodé** en variables.
Cette dernière condition ferme l'objection la plus solide contre l'article : le modèle tabulaire n'est pas
*aveugle*, il n'est pas *informé*. Elle rétablit du même coup la cohérence physique du bras textuel — un
article qui ferme des rues que le calculateur d'itinéraires ignore rend le résultat ininterprétable dans
les deux sens.

Enfin, les étoiles de la grille des 30 articles, écrites avant tout appel au modèle, sont requalifiées en
**prédictions pré-enregistrées** : 120 signes gelés par empreinte git, contre lesquels l'accord du modèle
se mesure au lieu d'être commenté après coup.

**Avant :** le manuscrit citait un facteur 11 sur la fidélité, 15 variables à parité, un χ² à p = 0,98
présenté comme une preuve, et comparait l'agent informé à un oracle qu'on n'avait pas informé.
**Après :** les chiffres sont ceux du dépôt, les périmètres et les effectifs sont déclarés, et chaque
affirmation de l'étape 3 a son critère de réfutation.

> ⚠ **`MANUSCRIT_DETAILLE_2026_SLIDES.html` n'a pas été mis à jour** et porte donc encore les onze
> chiffres corrigés. La règle de parité Markdown ↔ HTML du dossier `paper/` demande de l'aligner —
> à faire lors d'une prochaine passe sur ce fichier.

---

## [2026-09-01] Manuscrit v1.2 : Validation Démographique, Ablation 4 Paliers & Événements Réels Sourcés

Mise à jour majeure du manuscrit et du protocole scientifique ([`MANUSCRIT_DETAILLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/MANUSCRIT_DETAILLE_2026.md), [`PROTOCOLE_SCIENTIFIQUE.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PROTOCOLE_SCIENTIFIQUE.md), [`PLAN_ARTICLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PLAN_ARTICLE_2026.md)) :
* **Jalon 0 (Validation Démographique) :** Clarification de l'équiprobabilité des agents synthétiques (poids unitaire = 1, pas de $COEP$ runtime requis) et tableau de Goodness-of-Fit face au recensement Insee RP 2022 / CEREMA ($\chi^2$, $p > 0,95$).
* **Ablation Incrémentale en 4 Paliers :**
  - *Palier 0 (Planchers)* : Hasard pur (25 %), Prior empirique (56,7 %) et Heuristique du plus rapide $\min(\text{durée OTP})$.
  - *Palier 1 (Modèle Nu / Bare LLM)* : Évaluation zéro prompt engineering avec **Mistral AI** (modèles français/européens), **Qwen-2.5-32B** (open-weights local déterministe) et **Gemini-Flash**.
  - *Palier 2 (Modèle Calibré)* : Mesure du gain net de prompt engineering.
  - *Palier 3 (Baselines)* : Logit Multinomial (MNL) et Oracle LightGBM supervisé scellé.
* **Évaluation Écologique sur Actualités Réelles Toulousaines :** Substitution des scénarios synthétiques par des articles de presse réelle sourcée (*La Dépêche*, communiqués Tisséo, arrêtés préfectoraux) : *Le Minotaure / La Machine*, *Pic d'Ozone / Alerte Canicule*, *Coupure du Périphérique Ouest*.
* **Archivage :** Snapshots immutables `v1.2` enregistrés sous `docs/paper/archive/`.

---

## [2026-09-01] Manuscrit v1.1 & Protocole Scientifique de Référence pour la Publication

Formalisation complète du cadre méthodologique et versionnage des documents de recherche :
* **Nouveau document :** [`docs/paper/PROTOCOLE_SCIENTIFIQUE.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PROTOCOLE_SCIENTIFIQUE.md) établissant les règles épistémologiques, le contrôle du *data leakage*, les tests d'hypothèses et les 4 protocoles expérimentaux.
* **Manuscrit révisé en version `v1.1` :** [`docs/paper/MANUSCRIT_DETAILLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/MANUSCRIT_DETAILLE_2026.md) :
  - *Étude factorielle par vignettes sémantiques* ($N = 50 \times 5 = 250$ tests, test de McNemar) en remplacement des cas anecdotiques isolés.
  - *Parité informationnelle stricte* pour l'évaluation unitaire (vecteur 15 variables identique pour LLM, MNL et LightGBM).
  - *Formalisation mathématique de l'hystérésis* (mémoire court-terme $\mathcal{M}_t$ et cinétique de ré-adoption sur 5 jours).
  - *Formulation conceptuelle & cadre comparatif* de l'architecture hybride en cascade (100 % LightGBM vs 100 % LLM vs Hybride 90/10).
* **Archivage des versions :** Snapshots immutables créés sous `docs/paper/archive/`.

---

## [2026-09-01] Retour au modèle servi, après l'exploration de la distance

La page de synthèse est rendue au modèle de production — 21 variables, `od_km` = distance
entre les centres des deux zones fines — qui reste **le meilleur score de toutes les
variantes essayées** : composite comparable **7,40** sur le jeu commun.

Quatre variantes de distance ont été construites, entraînées et notées de bout en bout.
Aucune ne fait mieux, et le classement est net :

| Variante | Accuracy sur l'enquête | Composite sur le jeu commun |
|---|---|---|
| **Production — 21 variables** | 0,7854 | **7,40** |
| Sans les deux distances à l'hypercentre — 19 variables | 0,7843 | 7,43 |
| Distance routière ajoutée — 22 variables | 0,7844 | 7,47 |
| Distance reconstruite depuis la durée | 0,9345 | 9,28 |
| Idem, homogénéisée entre réseaux | 0,9338 | 12,69 |

Les deux dernières lignes sont contre-intuitives et c'est l'enseignement de la journée :
**une accuracy de 93 % sur l'enquête accompagne le pire score en simulation**. Toute
distance reconstruite depuis la durée déclarée contient le mode retenu, puisque c'est lui
qui choisit la vitesse ; le modèle apprend à le relire, et en simulation il reçoit une
grandeur qui ne le contient pas. L'homogénéisation entre réseaux aggrave l'écart au lieu
de le réduire, parce qu'elle déplace chaque mode d'un facteur différent — 0,83 pour la
marche contre 1,49 pour les transports.

Ce qui a été mesuré et qui reste vrai : le problème n'a jamais été la distance, c'était la
**durée**. Une distance homogénéisée construite depuis les distances routées, sans durée,
ne fuit pas — score de trahison de la marche 0,686 contre un plancher de 0,722. Elle est
seulement redondante, à 0,983 de corrélation avec la distance déjà en place.

**Avant :** on ne savait pas ce que valaient ces pistes.
**Après :** on sait, chiffres à l'appui, qu'elles sont épuisées — et pourquoi.

Comptes rendus et archives conservés : `docs/traces/2026-08-31_second_modele_19_features/`
et quatre versions datées de la page dans `docs/synthesis/archive/`.

---

## [2026-08-31] Retour au contrat à 21 features : la matrice de vitesse et otp_km retirées

Deux pistes explorées aujourd'hui pour enrichir la distance du modèle de choix modal sont
retirées du dépôt. Toutes deux ont été mesurées de bout en bout avant d'être abandonnées, et
c'est la mesure qui a tranché — pas une préférence.

**La matrice de vitesse** (`od_km` reconstruit depuis `D9 × vitesse moyenne du mode`) était
bien meilleure sur l'enquête et **25 % moins bonne là où le modèle sert** : composite du jeu
commun 9,28 contre 7,40. Cause : sa recette exigeait la durée du mode **effectivement pris**,
qui n'existe pas avant que le mode soit choisi. Le runtime fournissait donc une autre grandeur
sous le même nom. Ce n'était pas du surapprentissage — sur l'enquête, le modèle généralisait
parfaitement (validation 0,9336, test 0,9345) — mais une divergence entraînement / service.

**`otp_km`** (distance routière de `mode_skims.parquet`, servie à l'inférence par un loader
`core/mode_skims.py`) n'avait pas ce défaut : la même ressource, la même clé et la même
fonction de tranche horaire des deux côtés, non-fuite vérifiée à écart-type nul sur 2 668
paires-tranches parcourues par au moins deux modes. Elle ne rendait simplement **rien** :
composite 7,474 contre 7,401, accuracy 0,7844 contre 0,7854. Redondante à **0,972** avec
`od_km`, et absente **une fois sur deux** en simulation — `mode_skims` n'a été routé que sur
les paires OD de l'enquête, pas sur celles que la population synthétique génère.

**Avant :** le builder portait deux drapeaux de variante, une ressource de matrice de vitesse,
un loader runtime et deux versions de contrat supplémentaires.
**Après :** `build_mode_choice_dataset.py` est **identique au bit près** à son état d'avant
l'exploration — vérifié par diff, et par reconstruction du jeu (52 248 lignes, 32 colonnes,
aucune colonne différente de l'original, spec v2, 21 features).

`docs/synthesis/index.html` est régénérée sur le modèle de production — composite comparable
**7,40**, accuracy 78,5 %, 1 500 tours. La page du modèle v4 est archivée dans
`docs/synthesis/archive/2026-08-31_v4_matrice_vitesse/`.

**Trois enseignements gardés, et ils valent plus que le code retiré.**

1. **Une variable n'entre au contrat que si le runtime sait la produire.** L'ordre de travail
   correct est : loader d'inférence, puis point d'appel, puis colonne d'entraînement. Faire la
   colonne d'abord, c'est refaire l'erreur de la matrice de vitesse.
2. **Le découpage train/test se retire quand le nombre de lignes change.** 74,1 % des lignes de
   l'ancien test avaient été vues à l'entraînement par le modèle suivant ; la comparaison naïve
   donnait 0,9434 au lieu de 0,9205 sur le périmètre réellement hors échantillon.
3. **Une définition dupliquée dérive.** Les bornes de tranche horaire existaient en deux
   versions — nuit 0-7 h dans `build_mode_skims.py`, 0-5 h dans le code exploratoire — et
   attachaient la mauvaise ligne routée pour tout départ entre 5 et 7 h. Écrire le loader
   d'abord a fait apparaître l'écart avant qu'il ne coûte un entraînement.

Mesures conservées : `docs/traces/2026-08-31_second_modele_19_features/`.

---

## [2026-08-31] La matrice de vitesse : od_km reconstruit depuis la durée, mesuré de bout en bout

> ⚠ **Code retiré du dépôt le 31/08/2026.** La variante a été mesurée puis
> abandonnée ; seules les mesures survivent. Voir l'entrée du 31/08 « Retour au
> contrat à 21 features ».

Nouvelle ressource `speed_matrix.json` (`scripts/progedo_logit/export_speed_matrix.py`) : la
vitesse moyenne réalisée par cellule **mode × classe de durée × tranche horaire × distance
au centre origine × destination**, 495 cellules, estimée sur le split train seul, repli
hiérarchique sous 30 observations. Et un drapeau `--od-km {centroides,matrice_vitesse}` sur
`build_mode_choice_dataset.py` qui convertit une durée en distance avec elle, en retirant
`D9`, `D11` et les deux `dist_center_*`.

**Un résultat contre-intuitif sur la sélection des dimensions.** La tranche horaire ne
qualifie pas à mode fixé (`eta²` 0,0050) mais qualifie **à mode × classe de durée fixés**
(0,0097). L'effet était dilué, pas absent : la congestion pèse sur les trajets longs et
presque pas sur les courts — `eta²` de l'heure à 0,0029 sur les trajets voiture de moins de
8 minutes, **0,0688 au-delà de 60 minutes**. La classe de durée doit donc être une dimension
*avant* l'heure. Elle est d'ailleurs elle-même excellente (0,0177).

**Effet secondaire favorable, et il est réel.** `od_km` ne dépendant plus du rattachement
aux zones fines, le filtre de périmètre tombe : le jeu passe de 52 248 à **54 559
déplacements**, et le biais de sélection de −1,11 point sur la voiture disparaît. Les parts
pondérées du nouveau jeu — voiture 56,94 · marche 26,95 · TC 12,05 · vélo 4,06 — collent à
la table EMC² publiée (56,70 / 26,80 / 12,37 / 4,12).

**Avant :** on ne savait pas ce que valait cette piste, discutée trois fois sans chiffre de
bout en bout.
**Après :** le modèle v4 est **nettement meilleur sur l'enquête et 25 % moins bon là où il
servirait**. Sur les 3 382 déplacements hors échantillon pour les trois modèles, accuracy
0,7729 → **0,9205** et rappel vélo 0,1211 → **0,5272**. Sur le jeu commun renormalisé sur
l'offre OTP, composite comparable 7,401 → **9,282**, et toutes les dimensions se dégradent
sauf la distance.

La cause est structurelle. `od_km` version matrice se calcule depuis `D9`, la durée du mode
**effectivement pris**. À l'instant de la décision en simulation, ce mode n'est pas encore
choisi : il n'existe pas de `D9`. Le runtime fournit donc l'`od_km` entre centroïdes, une
autre grandeur (corrélation 0,78 entre les deux), et le modèle qui avait appris à lire la
première reçoit la seconde. Ce n'est pas un surapprentissage — sur l'enquête, v4 généralise
parfaitement (validation 0,9336, test 0,9345) — c'est une divergence entraînement / service.

**Deux pièges évités, à retenir pour les prochaines comparaisons.** Le découpage train/test
se retire quand le nombre de lignes change : 74,1 % des lignes de l'ancien test avaient été
vues à l'entraînement par v4, et la comparaison naïve donnait 0,9434 au lieu de 0,9205. Et
la version du contrat de features est un verrou, pas une étiquette : `spec_version` vaut 4
et non 3, parce que 3 désigne déjà un autre contrat à 19 features.

`docs/synthesis/index.html` est régénérée avec v4 ; la version précédente est archivée dans
`docs/synthesis/archive/2026-08-31_avant_v4/`. La production reste sur `centroides` — le
drapeau est explicite et son défaut inchangé.

Traces, artefacts et les cinq étapes détaillées :
`docs/traces/2026-08-31_second_modele_19_features/`.

---

## [2026-08-31] Le score du modèle statistique mesuré sur les deux bases, et la page de synthèse remise à jour

Le composite du modèle de choix modal existait sous deux valeurs qu'on pouvait croire
comparables : **1,235** et **7,53**. Elles ne le sont pas, et l'écart n'est pas une
progression du modèle — c'est la base de mesure qui change.

| Base de mesure | A — 21 features | B — 19 features |
|---|---|---|
| Split test de l'enquête, 13 045 déplacements déclarés | 1,248 | **1,235** |
| Jeu commun, 3 249 décisions, avant renormalisation OTP | 3,457 | 3,451 |
| Jeu commun, **renormalisé sur l'offre OTP** | 7,401 | **7,430** |

Trois différences se cumulent entre la première ligne et la dernière. La **population** :
personas de synthèse au lieu de déplacements déclarés, dont ~5 % des localisations tombent
hors de la couche de zones fines, à 22 km en médiane du périmètre d'enquête. La **contrainte
d'offre** : sur le jeu commun le modèle ne peut proposer que ce qu'OTP a offert, et cette
seule correction fait passer le composite de 3,45 à 7,43 — plus du double. Le **référentiel
de lecture** : sur le split test, on compare à la table EMC² des trajets que l'enquête a
elle-même produits, ce que la décision E3 du ticket 005 qualifie déjà de borne supérieure
et non de comparaison loyale.

**Ce que ça règle pour l'arbitrage des 19 features.** Sur le jeu commun, B est
**équivalent** à A : +0,029 sur le composite de tête (+0,4 %), −0,002 en mode élu, −0,006
avant renormalisation. Le léger avantage de B mesuré sur l'enquête (−0,013) ne se
transporte pas, il est au niveau du bruit. Retirer les deux distances à l'hypercentre ne
change donc rien à ce que la politique produira en simulation : même performance servie,
deux variables de moins, une dépendance à la définition de l'hypercentre en moins.

**Avant :** `docs/synthesis/index.html` datait du 27/08 à 19:50 et son volet 3 décrivait un
booster de **140 arbres** — composite comparable 7,53, accuracy 79,1 %, L1 2,4 points. Ces
chiffres ne correspondaient plus à l'artefact en place depuis le réglage des hyperparamètres
du 30/08, et rien sur la page ne le disait.
**Après :** régénérée, elle affiche le booster réel — 1 500 tours, composite comparable
**7,40**, mode élu 6,65, avant renormalisation 3,46, accuracy 78,5 %, L1 2,7 points. Ces
valeurs reproduisent au millième une mesure indépendante refaite à côté, ce qui vaut
contrôle croisé du chemin de score.

Enseignement à garder : **un composite ne se lit pas sans sa base**. Trois nombres du même
modèle — 1,2 / 3,5 / 7,4 — sont tous justes, et deux d'entre eux sont trompeurs si on omet
de dire sur quoi ils portent.

Traces : `docs/traces/2026-08-31_second_modele_19_features/volet3_scores_jeu_commun.json`.

---

## [2026-08-31] Un second modèle de choix modal, à 19 variables au lieu de 21

Les deux distances à l'hypercentre — `dist_center_orig_km` et `dist_center_dest_km`, la
distance en kilomètres entre le centre de la zone fine de départ, puis d'arrivée, et le
centroïde du secteur Capitole — sortent du contrat de features dans une variante mesurée
et documentée. Un second modèle est entraîné sans elles, avec le harnais de production,
sur le même découpage et la même pondération `COEP`.

**Le retrait coûte onze centièmes de point d'accuracy.** 0,7843 contre 0,7854 sur les
13 045 déplacements de test, log-loss 0,5470 contre 0,5402, L1 des parts modales 0,0293
contre 0,0269. La PR-AUC de la marche ne bouge pas (0,8191 contre 0,8185) ; celle des
transports collectifs paie le plus, à −1,21 point — cohérent, la desserte TC est radiale
et ces deux variables étaient la seule mesure explicite de la radialité d'un trajet.

**La raison du faible coût est mesurable, et elle vaut pour la suite :** à Toulouse,
densité de ménages et distance au centre mesurent le même gradient — **Spearman −0,879**.
Les 9 points de gain libérés se redistribuent presque exactement sur `density_orig`,
`density_dest` et `od_km`. Un arbre ne lisant que l'ordre des valeurs, une variable
monotone d'une autre lui est quasiment interchangeable.

**Corollaire à ne pas perdre : le coût des retraits n'est pas additif.** Retirer les deux
paires — les distances au centre *et* les densités — fait tomber la log-loss à 0,5806 et
la PR-AUC du TC à 0,7151, quatre points au lieu d'un. Sans aucune variable géographique,
accuracy 0,6974 et PR-AUC marche 0,560. On retire l'une **ou** l'autre, jamais les deux.

Deux vérifications faites au passage sur `od_km`, la distance entre centres de zones fines
qui reste la première variable du modèle. **Aucune fuite d'étiquette** : sur 20 922 paires
origine-destination distinctes, l'écart-type d'`od_km` à l'intérieur d'une paire vaut
exactement zéro, y compris sur les 3 093 paires parcourues par au moins deux modes
différents — le même trajet fait à pied et en voiture reçoit la valeur identique. **Biais
de sélection résiduel** : `od_km` est calculable pour 95,76 % des déplacements, mais le
taux reste inégal selon le mode (voiture 93,84 % contre vélo 98,87 %, les trajets longs
sortant du périmètre d'enquête), ce qui sous-représente la voiture de 1,11 point.

Effet de bord acquis : plus aucune feature ne consomme la définition de l'hypercentre.
L'écart de 820 m entre le centre publié dans le spec et la constante codée en dur dans
`move_logger.py` cesse de pouvoir décaler une prédiction.

**Avant :** le contrat comptait 21 features et personne ne savait ce que valaient les deux
distances au centre ; les retirer était une intuition.
**Après :** un second jeu de métriques côté à côte avec la référence, un contrat réduit
prêt à promouvoir (`feature_spec_19f.json`, spec v3), et le chiffre exact de ce que le
retrait coûte.

La politique servie n'est **pas** remplacée : l'arbitrage reste à faire. Promouvoir la
variante demande de retirer les deux features de `FEATURE_SPEC`, de porter `SPEC_VERSION`
à 3, de retirer les deux champs de `GeoFeatures` dans `zone_resolver.py`, de reprendre les
tests qui figent la liste des six features géo, puis de régénérer parquet, spec et
politique.

Rapport lisible, contrat réduit et métriques :
`docs/traces/2026-08-31_second_modele_19_features/`. Ce dossier tombe sous la règle
`docs/traces/*` du `.gitignore` et n'est donc **pas versionné** : il vit sur la machine
qui l'a produit. Les quatre fichiers se régénèrent avec la commande du `README.md`.

---

## [2026-08-31] Le jeu d'entraînement du choix modal passe au crible

Un notebook d'audit — `scripts/progedo_logit/explore_mode_choice_dataset.ipynb` — exporte le
jeu de la politique de choix modal en CSV, le **recharge depuis le CSV**, et vérifie ce
qu'on tenait pour acquis : étanchéité du découpage, représentativité train↔test de chaque
variable, valeurs aberrantes, colonnes contaminées.

Le découpage tient (0 ménage à cheval sur 9 393, 25,0 % de test), aucune variable ne dérive
entre les deux côtés (SMD max 0,037 ; TVD max 2,55 pts), et les dix règles d'impossibilité
de domaine passent toutes.

**Le seul défaut est un trou d'effectif, et il explique un chiffre de la page de synthèse.**
Le jeu de test ne contient qu'**une seule marche au-delà de 10 km et aucune au-delà de
20 km** ; neuf cases du croisement mode × distance tiennent sous 30 observations. C'est le
même mécanisme qui, sur la page de synthèse, laisse **un unique déplacement de plus de
50 km peser autant qu'une tranche de 856** dans la note de distance — la métrique ordinale
retient une tranche sur la présence d'une référence, jamais sur l'effectif mesuré.

**Avant :** le jeu était décrit par le seul résumé d'entraînement (accuracy, log-loss) ; les
cases trop minces pour être notées n'étaient visibles nulle part.
**Après :** neuf contrôles rendent un verdict explicite, et la carte des effectifs de test
montre où une note n'a pas de sens — avant qu'elle soit calculée.

Deux distinctions que l'audit tient et qu'un test naïf confond : *impossible* contre
*invraisemblable* (223 déplacements en voiture sans permis sont des passagers, pas des
erreurs), et *saturation* d'une variable continue contre valeur dominante d'une variable
discrète — les artefacts d'arrondi trouvés (`duration_min` à 17,6 % sur « 10 minutes ») sont
tous confinés aux colonnes déjà exclues du modèle.

---

## [2026-08-30] Le booster de choix modal réglé pour les modes rares

### Le vélo gagne en vraisemblance, sans repondération de classe

Les hyperparamètres LightGBM de la politique de choix modal n'avaient jamais été cherchés :
ils étaient posés à la main. Un banc de réglage les a cherchés sur **96 configurations**,
en validation croisée par ménage à l'intérieur du train — le split test n'est jamais lu
pendant la sélection.

Le diagnostic était contre-intuitif : le modèle était **en sur-capacité**, et c'est le mode
le plus rare qui le payait. Une classe à 4,3 % des déplacements ne peuple pas assez les
feuilles d'un arbre à 31 feuilles pour que sa probabilité y soit estimée sur autre chose que
du bruit. Passer à 5 feuilles, avec un pas trois fois plus court et dix fois plus de tours,
lui rend ce qui lui manquait.

**Avant :** vélo — vraisemblance 2,42 sur ses propres lignes, masse de probabilité à 96 % de
l'observé, PR-AUC 0,241.
**Après :** vraisemblance **2,35** (gain significatif au bootstrap apparié par ménage,
IC 95 % entièrement négatif), PR-AUC 0,276 en validation croisée.

Le log-loss global et l'écart sur les parts modales ne bougent pas au-delà du bruit : le
réglage transfère de la vraisemblance de la voiture vers le vélo, sans dégrader ce que le
pipeline consomme réellement. La calibration s'améliore (ECE 0,0142 → 0,0118).

**La décision E7 n'a pas été contournée.** Aucune repondération de classe : le banc écarte
d'office toute configuration qui dégrade de plus de 0,005 l'écart aux parts modales
observées — 22 des 49 configurations de la première passe y sont tombées.

**Ce qui ne change pas** : en mode élu (argmax), le vélo reste à 1,2 % pour 4,0 % observés,
avant comme après. C'est une propriété de l'argmax sur une classe rare, pas un défaut du
modèle ; la lecture juste des parts modales reste la masse de probabilité.

**Ce que ça coûte** : 6 000 arbres au lieu de 560, artefact 18,9 Mo au lieu de 12,2,
prédiction 44 µs par ligne au lieu de 10. Sans effet sur le pipeline actuel.

### Un banc de réglage réutilisable

`make policy-tune` cherche les hyperparamètres et écrit son classement complet sans toucher
au modèle servi : reporter un gagnant reste un geste humain, suivi de `make policy`. Le banc
mesure ce que l'accuracy et le rappel ne savent pas mesurer sur une classe rare — la
vraisemblance restreinte à la classe, la PR-AUC un-contre-tous, l'ECE, et l'écart aux parts
modales comme garde-fou.

---

## [2026-08-28] Le cache LLM se coupe au lancement, et deux planchers de hasard cadrent le score

### `make run CACHE=0` — un run entièrement journalisé

Le cache sémantique se désactive désormais depuis la ligne de commande, comme la mémoire
avec `MEM=0`. Ce n'est pas un réglage de confort : **une décision servie par le cache
n'est jamais journalisée**, et sans journal il n'y a pas de prompt à rejouer.

Mesuré sur le run du 27/08 : 6 735 décisions passées par la voie LLM, dont **76,4 %
servies par le cache**. Le journal ne contenait donc que 377 des 3 249 décisions du
périmètre scoré — 12 %, et pas n'importe lesquelles : celles qui avaient *raté* le cache,
donc les plus atypiques du run. Tout rejeu mesuré là-dessus aurait porté sur un
sous-ensemble biaisé sans que rien ne le signale.

**Avant :** un A/B de prompt ou une mesure de plancher ne pouvait porter que sur les
décisions ayant raté le cache.
**Après :** `make run CACHE=0` force chaque décision à passer par le modèle, donc à être
journalisée, et le rejeu couvre le périmètre entier.

Le coût est exactement l'inverse du taux de service du cache — **×4,24** — et il se
chiffre : 228 requêtes HTTP deviennent ~967, et 1,2 million de tokens d'entrée en
deviennent ~5,2 millions. Sur des paliers gratuits à 500 requêtes/jour par clé, un run de
1 000 agents tient tout juste sur deux seaux, ce qui **garantit la bascule entre modèles**.
Qui veut un plancher sur modèle unique doit réduire le périmètre plutôt que compter sur
la marge. `make run CACHE=1` remet le cache : sans ce retour, tous les runs suivants
paient le plein tarif.

### Deux planchers de hasard, mesurés sans un seul appel

`scripts/synthesis/bare_prompt_replay.py uniform` répartit la masse à parts égales et
score le résultat avec le même scoreur que les trois volets, sur le même périmètre.

| Plancher | Composite | Ce qu'il isole |
|---|---|---|
| Hasard **nu** — 4 modes, offre ignorée (`--all-modes`) | **38,29** | rien du tout : le plancher absolu |
| Hasard **contraint** — modes offerts par OTP | **21,76** | le hasard, mais informé de la faisabilité |
| Agents LLM | 16,16 | la chaîne complète |
| LightGBM | 7,53 | le modèle statistique |

**L'écart entre les deux hasards — 16,5 points — n'est produit par aucun modèle.** C'est ce
qu'apporte l'offre OTP à elle seule : savoir qu'on ne peut pas prendre un bus qui n'existe
pas fait plus de la moitié du chemin. Les agents ajoutent 5,6 points par-dessus, le
LightGBM 14,2.

Deux constats que ce cadrage rend visibles, et qu'il vaut mieux connaître avant qu'un
relecteur ne les trouve :

- **Sur la marche, le hasard contraint fait mieux que les agents** — écart à la cible
  +3,7 contre −12,3. Sur les transports collectifs aussi (+14,9 contre +17,8). Tout
  l'avantage des agents sur le hasard vient de la **voiture** (−8,6 contre −23,7) et,
  dans le détail des dimensions, du **motif** et de la **distance** : à eux deux ils
  expliquent **92 %** des 5,6 points d'écart.
- **Sur l'âge, le hasard est meilleur que les agents** (3,58 contre 4,37) — des personas
  qui portent l'âge dans leur prompt représentent moins bien la structure par âge qu'une
  pièce lancée.

### Ce que le rejeu « prompt nu » a déjà appris avant de tourner

`bare_prompt_replay.py replay` dépouille le bloc utilisateur de tout ce qui décrit la
personne, en **filtrant** le texte rendu par le moteur plutôt qu'en le reconstruisant.
Son essai à blanc a révélé une fuite : la mention d'abonnement TC n'est pas sur la ligne
de persona mais **dans la ligne d'option** (`_pt_subscription_note`, depuis le 26/08) —
**1 052 mentions sur 2 006 options**. Un dépouillement qui ne traitait que le persona
laissait donc le prompt annoncer si la personne a un abonnement. Le script échoue
bruyamment si le dépouillement ne retire rien : un prompt qu'on croit nu et qui ne l'est
pas produirait un plancher faux sans le dire.

---

## [2026-08-27] L'effet d'un ajout de prompt se lit en deux camemberts

`make alt-prompt-figure VARIANT=1` produit une figure PNG qui met côte à côte les parts
modales de la population entière avant et après un ajout au prompt système. Sur la
variante V1, l'écart tient en peu de chose : transports collectifs −1,7 point, voiture
+1,2, marche +0,3.

C'est le résultat, pas un défaut de la figure. L'ajout n'a été appliqué qu'aux 495
décisions où le modèle avait retenu un transport collectif alors que la marche lui était
proposée — sur 2 911. Là, il déplace 9,9 points de transport collectif ; dilué dans le run
entier, il en reste 1,7. `SCOPE=subset` dessine ces 495 décisions seules, `SCOPE=both`
empile les deux étages. La figure ne porte pas de titre, mais elle nomme toujours la
variante et le périmètre avec son effectif, et une phrase de lecture dit en pied ce que la
version choisie cache : un camembert de sous-jeu pris pour une part modale de ville est un
contresens.

Les chiffres sont lus dans la page de la variante — Δ compris, pour qu'une figure ne puisse
pas contredire d'un dixième la page dont elle dérive — et les réserves de la campagne
(pas de bras témoin, simulation non rejouée) sont imprimées en pied de figure. Un bras qui
n'a pas été rejoué n'est pas dessiné : la commande s'arrête en nommant celle qui produirait
la page manquante.

**Avant :** l'effet d'un prompt se lisait dans deux tableaux d'une page HTML, et le lecteur
pressé retenait celui des deux qui l'arrangeait.
**Après :** une image, un périmètre nommé, et la dilution dite à côté de l'effet.

---

## [2026-08-27] GAMA écrit à nouveau ses résultats : le symlink de sortie ne pend plus

Lancer une suite de tests sur l'hôte pendant une simulation faisait échouer l'écriture des
CSV de GAMA, avec une trace Java qui ne nommait pas la cause :
`FileAlreadyExistsException` sur `GAMA/CityTransport/results`, doublée d'un
« Java error: I/O error ».

Deux défauts se combinaient. Importer `settings` créait un répertoire de run et repointait le
symlink de sortie de GAMA — un import de test volait donc sa sortie à la simulation en cours.
Et hors conteneur, ce répertoire était fabriqué dans `llm-agents/experiments/` au lieu de
`experiments/` : la cible du symlink, codée en dur, ne résolvait plus rien depuis
`GAMA/CityTransport/`. GAMA voyait un lien pendant, tentait de créer le répertoire, et se
heurtait au lien lui-même.

Désormais : sous pytest ou `unittest` (ou avec `APP_NO_RUN_ARTIFACTS=1`), l'import lit la
configuration et s'arrête là — aucun répertoire créé, aucun symlink touché. Le répertoire des
expériences est celui de la racine du dépôt dans les deux contextes, ce qui rend à nouveau
valide la cible `../../experiments/…` — écrite par le contrôleur, mais lue par GAMA sur
l'hôte ou par le conteneur `gama`. Le contrôleur vérifie enfin cette résolution au
démarrage : elle est journalisée quand elle aboutit, et signalée en `[ALARME]` sinon — plutôt
que de laisser GAMA échouer une heure plus tard sur une erreur muette.

**Avant :** `make tests` pendant un run → GAMA perd ses sorties CSV, avec une erreur Java
opaque ; un `llm-agents/experiments/` fantôme se remplit de runs vides.
**Après :** les tests n'ont plus d'effet sur le run ; le symlink pointe toujours vers le
workdir courant, et une anomalie se lit dans les logs du contrôleur au démarrage.

---

## [2026-08-27] La page déclare quand les jeux gelés ne portent plus la population du run

La page de synthèse affirme que ses trois volets partagent un substrat. C'est vrai du run —
les gardes le vérifient — mais le volet 2 est *aussi* scoré sur des **jeux gelés**, découpés
dans un run antérieur. Leur manifeste enregistre l'empreinte de la population d'origine ; la
page la compare maintenant à celle du run épinglé et **déclare la divergence** quand elle
existe.

État constaté : le manifeste épingle une population `aec28f0146…`, le run en porte une
`4cd38bdc19…`. Les jeux gelés gardent donc l'abonnement TC et le permis recopiés du donneur
ENTD 2008, que les tickets 016 et 017 viennent de réécrire dans la population en service.

**Avant :** la phrase « les jeux gelés sont eux-mêmes construits à partir d'un run de ce
type » laissait croire à un substrat partagé, sans jamais le vérifier.
**Après :** les deux empreintes sont comparées, et l'écart est écrit avec sa conséquence de
lecture — les scores du volet 2 sur jeux gelés restent comparables entre eux, ce qui est leur
rôle, mais pas au volet 1 ni au volet 3.

La divergence est déclarée et **non corrigée** : refaire les jeux gelés casserait la
comparabilité de toute la trajectoire de calibration déjà mesurée. L'encadré ne s'affiche que
si la divergence existe — une mise en garde permanente cesse d'être lue.

---

## [2026-08-27] Un trait corrigé invalide désormais les décisions en cache

Le `state_hash` du cache sémantique LLM était fait des codes d'options, de la météo et de la
signature d'anticipation — **pas des traits du persona**. Or tous les traits ne conditionnent
pas l'offre : `has_pt_subscription` ne change que le texte du prompt. Corriger l'abonnement
de 352 agents laissait donc leurs décisions déjà en cache être resservies **sous l'ancien
prompt**, sans qu'aucun log ne le signale — troisième occurrence de la famille de pièges que
le ticket 013 avait ouverte pour les durées et le 014 pour l'anticipation.

Une signature des traits entre maintenant dans la clé. Conséquence pour l'usage : corriger un
trait de population suffit désormais, sans vidage manuel du cache — les décisions concernées
sont recalculées, les autres restent servies.

**Avant :** après une correction de trait, il fallait vider `data/cache/llm` à la main, et
rien ne rappelait qu'il le fallait.
**Après :** la clé porte les traits ; un agent dont un trait a changé rate le cache, les
autres continuent d'en bénéficier.

Deux précisions qui séparent le correctif de la gêne. `has_driving_license` s'auto-invalidait
déjà — il passe par `_can_drive`, qui déplace les modes offerts, donc les codes d'options.
Et `name` est **exclu** de la signature : il vient de Faker non graine, donc l'inclure
viderait tout le cache à chaque régénération de population. Vérifié plutôt que supposé — le
`name` est identique entre la population source et celle du run (930/930), il n'est donc pas
re-tiré au chargement, contrairement à ce qu'affirmait la documentation.

Une signature vide laisse le hash inchangé : un cache antérieur reste lisible, au prix de
n'être pas gardé sur cet axe.

---

## [2026-08-27] Blocs d'âge scolaires : testés, rejetés — et les traits posés sur les populations en service

### L'étape 6, arbitrée et négative

Trois représentations de l'âge dans la politique de choix modal, mêmes données et mêmes
hyperparamètres, arbitrées par validation croisée **GroupKFold(5) groupée par ménage** sur
les 52 248 déplacements et 9 393 ménages du jeu corrigé. Règle annoncée avant de voir le
résultat : retenu si la log-loss pondérée gagne au moins 0,002.

| Variante | Log-loss hors échantillon | Gain | Verdict |
|---|---|---|---|
| âge continu (référence) | 0,58888 | — | — |
| + `under_26` | 0,58736 | +0,00152 | **rejeté** — sous le seuil |
| âge remplacé par blocs de cycles scolaires | 0,59505 | −0,00617 | **rejeté** — dégrade |
| blocs **et** âge continu | 0,59760 | −0,00872 | **rejeté** — dégrade |

Remplacer l'âge continu par des blocs `[0-5] [6-10] [11-14] [15-18] [19-26] …` **dégrade**
le modèle : le bloc perd le gradient interne, et un booster trouve déjà ses coupures. Le
palier `under_26` apporte un gain réel mais trois fois trop petit pour le seuil annoncé.

Rien n'est changé dans le modèle. Le résultat est consigné parce qu'une hypothèse éprouvée
et rejetée vaut d'être écrite — sinon elle se repropose dans six mois.

Ce verdict était attendu depuis la correction de la granularité des codes de zone du même
jour : la motivation des blocs était que le modèle apprenait mal les cohortes scolaires,
mais la cause était l'attrition de l'échantillon, pas la représentation de l'âge. Le jeu
étant redevenu représentatif par bande d'âge, le modèle apprend le gradient tout seul.

### Les deux traits posés sur les trois populations en service

`enrich_equipment` puis `fix_minor_traits` appliqués à `data/population/`. Aucune
régénération : c'est la voie 1 des tickets 016 et 017.

| Population | Abonnement TC posé | Permis posé | Valeurs modifiées | `car_availability` recalculé |
|---|---|---|---|---|
| 100 | 24,8 % *(cible 25,8)* | 86,9 % *(cible 85,9)* | 47 + 20 | 27 ménages |
| 1000 | 22,9 % | 87,7 % | 352 + 148 | 68 ménages |
| 1014 | **25,8 %** | 83,9 % | 348 + 173 | 121 ménages |

Les portes d'ensemble passent sur les trois, l'écart étudiant − retraité vaut +45,5 pt sur
la population 1000 et +65,1 sur la 1014 (contre +5,7 avant, pour +54,5 observés), et
`car_availability` est cohérent avec les permis posés partout. Les trois sortent en code 4 —
écart de composition sur la strate étudiante, qui se corrige au tirage et non ici.

**Avant :** un étudiant sur trois arrivait au LLM avec son abonnement.
**Après :** les trois populations en service portent des traits appris sur l'enquête, et le
prochain run les lira sans rien régénérer.

---

## [2026-08-27] La moitié des déplacements manquait à l'entraînement du modèle — corrigé

`build_trips` comparait les codes de zone du fichier déplacements (`102103503`, au niveau
sous-zone) à ceux de la couche `zf_zones.gpkg` (`102103000`, toujours suffixés `000`).
Résultat : **51,1 % des origines-destinations résolues**, et une attrition qui n'était pas
uniforme — trois quarts des déplacements des 10-14 ans écartés contre la moitié de ceux des
adultes, ce qui divisait par près de trois la part de transports collectifs apprise pour les
cohortes scolaires. Le modèle était mal entraîné exactement là où la page de synthèse
affiche son plus gros écart.

`zone_key()` ramène le code à la granularité de la couche. Résolution **51,1 % → 95,8 %**,
jeu d'entraînement **27 886 → 52 248 déplacements**, et il est désormais représentatif :

| Bande | Part TC avant | après | réelle |
|---|---|---|---|
| 10-14 | 9,7 % | **27,3 %** | 27,1 % |
| 15-19 | 31,5 % | **45,4 %** | 45,2 % |
| global | 9,8 % | **12,3 %** | 12,4 % |

Validé plutôt qu'affirmé : sur les 24 365 déplacements récupérés, la distance obtenue
corrèle à 0,984 avec la distance à vol d'oiseau déclarée, contre 0,992 sur ceux déjà
résolus — la troncature situe les trajets aussi bien, elle ne rapproche pas des
destinations lointaines. Les 4,2 % restants sont hors périmètre pour de bon et le restent.

Politique ré-entraînée : test sur 13 045 déplacements au lieu de 6 985, L1 du mode élu
0,0861 → 0,0573, `has_pt_subscription` devenu deuxième variable du modèle (10,2 % du gain).

**Sur l'écart des 15-19 ans, le plus gros de la page, les deux corrections du jour se
cumulent :** transports collectifs −24,5 → **−14,8** points, voiture +28,0 → **+20,9**.
Le motif « études » passe de −9,9 à −4,5 sur les TC, les 10-14 ans de −15,3 à −9,3.

**Mais le composite de tête empire (6,015 → 6,208), et c'est un biais de la lecture, pas
des corrections.** La renormalisation sur l'offre OTP retire 9 points à la voiture — que le
modèle surprédit en brut — et les répartit sur les modes offerts. Elle **améliore** ainsi
deux modes sur quatre : marche −7,7 → −2,7 d'écart, voiture +6,4 → −2,6. Le problème est
concentré sur les transports collectifs, presque toujours offerts, donc premiers
bénéficiaires de cette masse : ils sont à **+0,9** de leur cible dans la vision propre du
modèle et à **+4,1** après renormalisation. **`attendu` pénalise donc toute correction qui
augmente les TC, même juste** ; `elu` (6,464 → 5,933) et `brut` (6,282 → 5,652) n'ont pas
ce biais et vont dans le bon sens. Le déplacement par mode est désormais **mesuré et publié**
dans `data.json` (`renormalisation_bias`), recalculé à chaque régénération : une valeur
figée deviendrait fausse au run suivant sans que rien ne le dise.

**Avant :** un ré-entraînement à variables inchangées laissait les parquets périmés servis
comme courants, sans signal.
**Après :** le parquet porte `policy_sha256` et la page le compare à l'artefact sur le
disque — troisième axe du garde de substrat, après le nom du run et l'empreinte du journal.

---

## [2026-08-27] `cerema_values.yaml` vérifié contre le rapport source — et la vraie cause de l'écart des 15-19 ans

Les cibles de la page ont été confrontées au rapport d'enquête publié (aua-toulouse.org,
68 pages). **Elles sont conformes** : recalculées sur les 54 559 déplacements exploitables
des micro-données, pondérées `COEP`, les parts modales reproduisent la table publiée à
0,4 point près en global, et à moins de 1 point sur chaque bande d'âge sauf les 15-19 ans
(2,2 points). Les tables occupation, type de logement, motif et genre concordent exactement.
Le rapport confirme aussi ce que « transports collectifs » recouvre — Tisséo, train liO, et
les autres transports en commun dont les autocars régionaux et scolaires — et que « autres
modes » désigne les deux-roues motorisés, camionnettes et trottinettes.

**En revanche le jeu d'entraînement de la politique perd la moitié des déplacements, et pas
au hasard.** `build_mode_choice_dataset` n'en garde que 27 886 sur 54 559, et l'attrition
tient à un seul filtre : `od_km`, qui exige que les deux extrémités du déplacement tombent
dans la couche de zones fines.

| Bande | `od_km` absent | Part TC réelle | Part TC dans l'entraînement |
|---|---|---|---|
| 10-14 | **75,5 %** | 27,1 % | **9,7 %** |
| 15-19 | **64,7 %** | 45,2 % | **31,5 %** |
| 30-49 | 48,4 % | 5,8 % | 7,0 % |

Trois quarts des déplacements des 10-14 ans sont écartés, contre la moitié de ceux des
adultes, et le sous-ensemble retenu divise leur part de transports collectifs par près de
trois. La politique est donc mal entraînée exactement sur la cohorte où la page affiche son
plus gros écart — les 15-19 ans, voiture +28 points et TC −24,5 avant correction des traits.

**Avant :** on pouvait attribuer cet écart à la population ou à la cible.
**Après :** la cible est vérifiée juste, la correction des traits n'en récupère que
5,3 points, et le reste s'explique par un échantillon d'apprentissage biaisé en âge. Le
correctif est du côté de la résolution des OD, pas de la table de référence.

---

## [2026-08-27] Ce que la correction des traits vaut sur le volet 3 : le chiffre de tête ne bouge pas, et c'est le résultat

Contrefactuel chiffré avant tout run : sur `experiments/archive/2026-08-26_17_46`, mêmes OD,
même offre OTP, même politique PROGEDO, seuls l'abonnement TC et le permis passent de la
recopie ENTD à la loi apprise sur l'enquête.

| Lecture du volet 3 | Avant | Après |
|---|---|---|
| brut (vision propre du modèle) | 6,282 | **5,749** |
| mode le plus probable | 6,464 | **6,086** |
| masse renormalisée sur l'offre OTP | 6,015 | 5,941 |

La prédiction brute gagne 0,53 point de composite et 9,2 points de L1. Le chiffre publié —
la masse renormalisée — ne gagne que 0,07 et perd même 0,72 en L1.

**Le gain est là où le ticket 016 l'annonçait** : les 15-19 ans, plus gros écart de la page,
voient leur surestimation de voiture passer de +28,0 à +23,7 points et leur sous-estimation
de TC de −24,5 à −19,2. Les 10-14 ans gagnent 4,0 points sur les TC, le motif « études »
2,9 sur la voiture. Et là où aucun gain n'était à attendre, il n'y en a pas : la marche des
chômeurs reste à −11,9 — cet écart-là vient des longueurs de trajet, que nul trait ne corrige.

**Deux dimensions se dégradent, pour une raison qui est le diagnostic même du ticket 016.**
Les TC étaient déjà surprédits chez les adultes : hommes 13,5 % pour une cible de 11,6,
Toulouse 23,4 pour 21,6. Relever les abonnements — à juste titre — les pousse plus haut
encore. La surprédiction chez les adultes et la sous-prédiction chez les jeunes se
compensaient ; corriger les personnes les **sépare**. « La part TC globale reste presque
juste, et elle est juste pour les mauvaises personnes » — c'est vérifié par l'autre bout.

**Avant :** on pouvait croire que corriger les traits ferait baisser le composite du volet 3.
**Après :** on sait que non, et pourquoi — le composite était juste pour de mauvaises
raisons. Le volet 3 n'est donc pas le bon juge de ce lot ; ce que la correction produit se
mesure au volet 1, sur un run.

Réserve inscrite : l'offre OTP est gelée dans ce contrefactuel, alors que le permis
conditionne l'offre voiture dans le simulateur. L'effet du permis y est donc **sous-estimé**,
et son chiffre définitif viendra du run.

---

## [2026-08-27] Abonnement TC et permis posés sur la population — lot 2 des tickets 016 et 017

`enrich_equipment` remplace la recopie du donneur ENTD 2008 par un tirage dans les lois
apprises sur EMC² 2023, et le notebook de génération l'enchaîne désormais avec les autres
correctifs de surface. Applicable aux populations existantes, sans régénération.

Sur `toulouse_population_1000.json` :

| Trait | Avant | Après | Cible |
|---|---|---|---|
| abonnement TC, ensemble | 21,9 % | 22,9 % | 25,8 % |
| permis, 18 ans et + | 91,5 % | 87,7 % | 85,9 % |
| **écart étudiant − retraité** | **+5,7 pt** | **+45,5 pt** | +54,5 pt |

Le dernier est le critère le plus discriminant du ticket 016 : l'abonnement passait des
étudiants aux retraités, la répartition est rétablie aux quatre cinquièmes. 352 valeurs
d'abonnement et 148 de permis changent.

**Un piège fermé au passage.** `car_availability` dérive du nombre de permis du ménage :
tout recalcul fait avant la pose des permis est périmé, et rien ne le signalait. Le
notebook rejoue donc `fix_minor_traits` **après** l'enrichissement — 68 ménages recalculés —
et la recette **échoue** si les deux ne sont plus d'accord.

**Avant :** un étudiant sur trois arrivait au LLM avec son abonnement ; les mineurs
n'avaient pas de permis mais 85 % des 18-24 ans en avaient un, contre 58 % mesurés.
**Après :** les deux courbes suivent l'enquête, et les trois niveaux de repli géographique
sont comptés et publiés — jamais un `false` par défaut silencieux.

**Ce que la recette refuse de laisser passer**, et qui n'est pas un défaut du trait : les
étudiants synthétiques s'abonnent à 59,8 % contre 72,2 % attendus, et détiennent le permis
à 72,0 % contre 59,2 %. Cause mesurée : ils vivent dans des ménages **trop motorisés** —
36,6 % sans voiture contre 48,5 % dans l'enquête. La motorisation est la covariable la plus
forte de la loi, donc l'écart se propage mécaniquement. `number_of_cars` est juste en
agrégat ; c'est sa distribution jointe avec l'occupation qui ne l'est pas. Ça se corrige au
**tirage** de population, pas dans un post-traitement de trait : la recette le dit avec un
code de sortie distinct (4, écart de composition) de celui d'un vrai échec (2), pour ne pas
bloquer la chaîne de génération sur un défaut qu'aucun enrichissement ne peut réparer.

---

## [2026-08-27] Abonnement TC et permis appris sur l'enquête — lot 1 des tickets 016 et 017

`make equipment-propensity` apprend les deux propensions d'équipement sur les microdonnées
EMC² 2023 et écrit deux ressources autoportantes. Ces deux traits étaient jusqu'ici
**recopiés** d'un donneur ENTD 2008 apparié dans une classe d'âge couvrant 15 à 29 ans d'un
bloc — alors que l'abonnement TC y passe de 64 % à 29 % et le permis de 0 % à 78 %.

Un seul chargeur pour les deux traits, comme les tickets le demandent. La loi tient ses
cibles hors échantillon : toutes les strates d'occupation à 0,1 point, le gradient de
motorisation exact (61,8 → 25,5 → 16,1 %), l'ensemble à 25,9 % pour l'abonnement et 85,9 %
pour le permis. AUC hors-échantillon 0,798 et 0,953, validation croisée **groupée par
ménage** — un découpage par personne mettrait le même foyer des deux côtés.

**La tarification Tisséo entre comme emplacement de rupture, jamais comme grandeur.** Ni
montant, ni échelon, ni condition de ressources : le revenu du ménage est livré vide dans
l'enquête, et les tarifs qui en dépendent sont donc inobservables. Les paliers d'âge
(« moins de 26 ans », ouverture senior) sont ajustés puis **arbitrés** sur une règle écrite
d'avance — retenus si l'AUC hors-échantillon gagne au moins 0,002. Ils sont retenus sur
l'abonnement (+0,0079) et **retirés sur le permis** (−0,0001), où ils n'avaient aucune
raison métier d'être : l'arbitrage tranche dans les deux sens.

**Avant :** un étudiant sur trois arrivait au LLM avec son abonnement, contre deux sur
trois dans la réalité toulousaine ; 85,4 % des 18-24 ans avaient le permis contre 58,1 %
mesurés.
**Après :** la loi qui posera ces traits reproduit les deux courbes sur l'enquête, et son
vecteur de design est partagé entre l'apprentissage et l'application — l'aller-retour est
vérifié à 4·10⁻¹⁶.

Deux réserves inscrites plutôt que tues : la cible « étudiants » du ticket 016 est
**restatée de 74,3 % à 72,2 %**, parce que le recodage du dépôt range les alternants avec
les étudiants et qu'ils s'abonnent à 56,7 % — c'est la définition du dépôt qui doit gagner,
puisque c'est celle que le persona porte. Et l'écart des 25-34 ans sur le permis (−3,2 pt)
dépasse la tolérance du ticket 017 : il demande soit l'interaction âge × genre que le
ticket prévoit, soit un critère restaté, à trancher au lot 2.

Les traits ne sont **pas encore posés** sur une population : c'est le lot 2 (scripts
d'enrichissement et appel dans le notebook de génération).

---

## [2026-08-27] Le modèle PROGEDO rejoué sur le run du 26/08 — et la population qui n'a pas bougé

`docs/synthesis/detail_progedo_26_08.html` publie le détail par sous-catégorie du volet 3
mesuré sur `experiments/archive/2026-08-26_17_46`, à côté de `detail_progedo.html` qui garde
la mesure du run épinglé (`2026-08-24_17_34`). Les deux mesures coexistent : la mesure
épinglée n'est pas écrasée, et sa trace `progedo_on_common_set.parquet` non plus — celle du
nouveau run vit dans `progedo_on_common_set_2026-08-26_17_46.parquet`.

Le composite du volet 3 recule nettement : `emd_jsd` **8,01 → 6,02** en masse renormalisée,
**9,05 → 6,46** en mode le plus probable. La part de marche prédite passe de 23,1 % à 24,9 %
(cible 26,8 %), les transports collectifs de 11,7 % à 14,0 % (cible 12,4 %).

**Ce gain ne vient pas de la population.** Le `population_1000.json` du nouveau run est
**byte-identique** à celui du run épinglé (`4cd38bdc…`) : mêmes 930 personas, mêmes domiciles,
mêmes traits, mêmes horaires d'activités. La modification portée à
`data/population/toulouse_population_1000.json` ne touchait que les horaires d'activités
(945 agents sur 1021, champs `start_time` / `end_time` / `scheduled_start_time`), et la passe 2
de préparation les recalcule intégralement depuis les temps de parcours OSMnx — l'édition est
écrasée avant d'atteindre la simulation.

Ce qui a bougé, c'est **l'offre OTP** : décisions à mode unique 810 → 723, offres à deux modes
627 → 765, et 504 décisions (contre 475) dont la renormalisation déplace le mode le plus
probable. Le volet 3 ne lit ni le prompt ni les décisions du LLM ; sur un substrat de personas
identique, l'offre est son seul canal de variation.

**Avant :** le volet 3 se lisait sur le seul run épinglé du 24/08.
**Après :** deux mesures comparables coexistent, et l'écart entre elles est attribuable à
l'offre de mobilité, pas au peuplement.

---

## [2026-08-26] Une seule configuration de run — plus de choix par le Makefile

`llm-agents/config/` ne contenait plus qu'un empilement de variantes d'expériences passées
(`config_baseline*.yaml`, `config_gpt-oss-*.yaml`, `config_llama*.yaml`, `config_mistral*.yaml`,
`config_qwen*.yaml`, `config_deepseek*.yaml` — une trentaine de fichiers), sélectionnables au
lancement via `make run CONFIG=...`. Cette collection est supprimée (récupérable via
l'historique git) au profit d'un unique `llm-agents/config/config.yaml`, repris du contenu de
l'ancien `config_test_meteo_agent.yaml`. `osmnx.yaml` et `terminal_time.yaml`, sans lien avec
ce mécanisme de sélection, ne sont pas touchés.

Pour changer de configuration de run, éditer directement `llm-agents/config/config.yaml` — il
n'y a plus de variable `CONFIG=` à passer à `make run` / `make run-offline`, ni de sélecteur
dans le dashboard de pilotage. Chaque run continue d'écrire la configuration effectivement
utilisée dans `experiments/archive/<run>/static_config.yaml`, et le déclenche désormais
inconditionnellement dès le premier accès à `settings` (au lieu d'être conditionné à la
présence d'un fichier de config choisi) — y compris hors `make run` (tests, scripts).

**Avant :** `make run CONFIG=config_baseline_1000_current.yaml` choisissait parmi ~30 fichiers ;
sans `APP_CONFIG_PATH` défini (hors `make run`/Docker), aucun run n'était archivé.
**Après :** `make run` (sans variable) utilise toujours `config.yaml` ; tout accès à `settings`
crée et archive un workdir d'expérience.

---

## [2026-08-26] Relecture du lot en cours : justifications LLM, garde-fous et documentation du tirage météo

Corrections issues d'une relecture complète du diff depuis la dernière version poussée
(`964ccbab`) : quatre bugs bloquants, une incohérence de configuration et deux garde-fous
manquants.

**La justification par option, ajoutée le 26/08 (`prompts.yaml`), n'était en réalité
jamais lue.** `AgentResponse.reason` a été retiré du schéma racine au profit d'une `reason`
par `OptionProbability`, mais `llm_agent.py` continuait de lire l'ancien champ racine —
plus jamais rempli par le LLM. Chaque décision loggait donc systématiquement « Pas de
justification fournie. », qu'un modèle ait ou non expliqué son choix.
**Avant :** aucune justification par option n'atteignait la mémoire court-terme ni les logs.
**Après :** la justification de l'option effectivement tirée est retrouvée et reportée dans
la STM et les logs.

**`enrich_housing_type` ne pouvait jamais faire échouer la génération de population.**
Seul ce trait tournait sans `--check` dans `generate_population.ipynb`, contrairement à
`enrich_residence_zone` et `enrich_personal_bike` : sans `--check`, le script rend toujours
un code de sortie « ok », même si toutes les portes de recette du ticket 019 échouent.
**Avant :** un logement mal imputé ne bloquait rien dans la chaîne du notebook.
**Après :** les trois traits imputés sont soumis aux mêmes portes de recette.

**Le dashboard Streamlit plantait à l'affichage des tickets.** `tickets_status.yaml`
portait `status: fait`, hors du vocabulaire déclaré (`à faire | en cours | terminé | bloqué
| en veille | abandonné`), provoquant un `KeyError` dans `STATUS_ICON[t.status]`. Corrigé
en `terminé`, et `tickets.py` refuse désormais explicitement toute surcharge hors
vocabulaire au lieu de laisser planter l'appelant plus loin.

**Un test du filtre de périmètre (ticket 026) ne pouvait plus s'exécuter** —
`test_perimeter_filter.py` importait `_perimeter_verdict` (inexistant) au lieu de
`perimeter_verdict` ; le code de production était correct, seul le test échouait
(`ImportError` sur 7 des 9 cas). Le filtre n'était donc en réalité pas couvert malgré
l'apparence.

**Le tirage météo par agent (`weather_draw.py`, cf. `docs/arch/llm-inference.md`) pouvait
lire le mauvais créneau au franchissement de la bascule heure d'été/hiver** — un offset UTC
figé sur la date de départ réelle plutôt que recalculé pour la date météo substituée.
Corrigé en fixant le fuseau sur `Europe/Paris`, comme le fait déjà `weather_loader.py`.

**`bike_ownership.json` n'avait pas de contrôle de version au chargement**, contrairement
aux ressources `housing_type`/`residence_zone` du même lot — ajouté (`RESOURCE_VERSION`),
avec le test de rejet correspondant.

Documentation mise à jour en conséquence : le dispositif « une date météo par agent »
(absent de toute doc jusqu'ici) est maintenant décrit dans `docs/arch/llm-inference.md`, et
le ticket 024 ne prétend plus que le jeton d'exclusion existe (retiré le même jour, cf.
entrée suivante).

---

## [2026-08-26] Le pré-enregistrement et le jeton d'exclusion sont retirés

Deux dispositifs de méthode disparaissent, sur décision explicite.

**`prompt_calibration/PROTOCOLE.md`** — le protocole pré-enregistré de la campagne de
calibration, 73 Ko, quinze amendements datés de A1 à A15. Il fixait les hypothèses,
l'instrument gelé, la métrique gelée, les règles statistiques, le regard unique sur le jeu de
test, et ce qui serait conclu en cas de non-significativité.

**Le jeton d'exclusion** — `make protocol-lock/unlock/status`, le script qui le prenait, le
garde-fou que tous les scripts de mesure appelaient, et leurs tests. Une mesure démarre
désormais sans rien vérifier.

**Avant :** un `ab_*.py` sans jeton refusait de démarrer (code 7), et sa trace pouvait citer
un jeton horodaté avec ses instantanés de quota.
**Après :** il démarre. Rien ne l'empêche de tourner pendant un run qui consomme le même
quota.

### Ce qui reste, et ce qui manque

La **condition de validité n'a pas disparu — seul son contrôle l'a.** Deux bras évalués par
deux modèles différents, parce que la cascade de fournisseurs a basculé au milieu, restent une
mesure dont on ne sait pas ce qu'elle décrit. Avant une mesure, il reste donc à vérifier à la
main qu'aucun run ni service consommateur ne tourne, et que la campagne cloud est en pause.

Ce que le verrou apportait et qui manque : la **preuve**. Une trace ne peut plus produire
qu'une affirmation. À une mesure près la différence est mince ; à l'échelle d'une campagne,
c'est ce qui distingue un dossier opposable d'un souvenir.

Les mesures déjà publiées gardent la leur : leurs jetons sont committés dans leurs traces.
L'étape 0 du protocole exogène est réécrite en conséquence — elle décrit désormais une
vigilance, pas un outil.

### Rien n'est perdu, mais il faut savoir où chercher

Les deux fichiers restent dans l'historique git. Un amendement se retrouve par
`git log --all -- PROTOCOLE.md` dans le dépôt `prompt_calibration`.

⚠ **Sept fichiers renvoient encore à `PROTOCOLE.md`** : quatre tickets, deux traces archivées
et un libellé de rôle dans le catalogue de prompts. Ils n'ont pas été réécrits — une trace
archivée décrit ce qui a été fait au moment où ça a été fait, et la corriger après coup
falsifierait le dossier. Leurs liens pointent donc vers un fichier absent, et c'est un choix.

---

## [2026-08-26] Le jeton d'exclusion devient optionnel, et son absence se déclare

Une mesure sur jeux gelés refusait de démarrer sans jeton d'exclusion. Elle l'exige toujours
par défaut, mais l'exigence se lève désormais en connaissance de cause :

```
PROTOCOL_LOCK_OPTIONAL=1 python ab_meteo.py --dataset val --out …
```

**Avant :** pas de jeton, pas de mesure — même quand l'exclusion était garantie autrement
(pile arrêtée et vérifiée à la main, ou jeton concurrent portant un quota qui ne recouvre pas
celui de la mesure).
**Après :** la mesure part, et elle **dit** qu'elle est partie sans preuve.

### Ce qui distingue une dérogation d'un contournement

Trois propriétés, et la troisième est celle qui compte :

- elle ne se prend **jamais** par défaut — seule la valeur exacte `1` la déclenche, et un test
  vérifie qu'un `PROTOCOL_LOCK_OPTIONAL=0` ne lève rien ;
- elle est **bruyante** — cinq lignes d'avertissement, et le message de refus la nomme, parce
  qu'une échappatoire introuvable n'en est pas une ;
- elle est **écrite dans le résultat** — chaque mesure porte désormais une clé `exclusion`
  dans son JSON, présente *systématiquement*, y compris quand tout allait bien. Un champ
  absent se lirait comme « pas de problème », ce qui est précisément l'ambiguïté que le jeton
  existe pour supprimer.

Une mesure en dérogation **n'est pas invalide — elle est sans preuve d'exclusion.** La
distinction est tout l'objet du dispositif : ce qui reste refusé, ce n'est pas de mesurer sans
jeton, c'est de **ne pas savoir** dans quelles conditions une mesure a été prise. Une trace
doit le dire au même titre qu'elle dit son modèle-juge et sa température.

Au passage, les jetons archivés de verrous déjà relâchés ont été supprimés du répertoire de
travail. Les preuves d'exclusion des mesures publiées ne bougent pas : elles vivent, commitées,
dans les traces qui les citent.

---

## [2026-08-26] Le téléphérique n'est plus compté comme de la marche

Le Téléo fait partie du réseau Tisséo. Le calcul du score l'ignorait : une option de
**téléphérique pur** — « foot,cableway,foot » — tombait sur le mot « foot » et était comptée
en **marche**, le mode déjà le plus sous-représenté du modèle. Les trajets mêlant le Téléo à
un bus ou un métro étaient, eux, correctement classés : seul le téléphérique seul était
touché.

**Avant :** `foot,cableway,foot` → marche
**Après :** `foot,cableway,foot` → transports collectifs

Ce n'est pas une convention nouvelle. Le journal de production comptait déjà ces modes
correctement — la série de runs n'a jamais été affectée. Seule la loss de calibration
divergeait, et personne ne lisait les deux listes côte à côte. Un test de parité les
verrouille désormais ensemble.

### Chiffré avant d'être appliqué, parce que c'est l'instrument de mesure

Corriger la fonction qui note change les notes déjà données. L'effet a donc été recalculé
depuis les décisions en cache, **sans un seul appel LLM**, avant toute modification :

| Jeu | Contraste | Avant | Après |
|---|---|---:|---:|
| `all` | bulletin météo | +0,190 | +0,196 |
| `all` | témoin nul | −1,066 | −1,012 |
| `val` | fenêtre météo | −1,694 | −1,492 |
| `val` | bulletin météo | +1,717 | +1,511 |
| `screen` | *les quatre* | — | *inchangé* |

Les composites bougent de 0,01 à 0,32 point, toujours vers le haut : déplacer de la masse de
la marche vers les transports collectifs dégrade les deux côtés à la fois, la première étant
sous-représentée et les seconds sur-représentés.

**Aucun verdict ne change.** Fenêtre, bulletin et agenda restent tous sous leur plancher de
bruit. C'est ce qui autorisait le correctif sans clore la série de mesures.

Les traces et le registre gardent les chiffres **tels que mesurés**, et portent désormais la
note du correctif avec les valeurs recalculées : un recoupement futur doit pouvoir dire quel
instrument a produit quel nombre. Les réécrire aurait falsifié l'archive.

### Le chiffrage a été recoupé, et il a trouvé une campagne de plus

Le recalcul a été **refait indépendamment**, avec un contrôle qui le rend opposable : sous
l'ancien instrument, il doit reproduire le score **déjà en base**, au chiffre près. Écart nul
sur les 39 évaluations en cache, deux bases, deux modèles d'évaluation. Les chiffres du
tableau ci-dessus sont confirmés au millième.

Ce recoupement a montré qu'une **deuxième campagne** était concernée, celle de l'échelle de
contexte : sur son jeu `val`, les composites montent de 0,13 à 0,22 et les écarts au palier de
référence bougent de 0,02 à 0,10 — plancher de bruit compris. Sa conclusion ne bouge pas d'un
cheveu (les quatre ablations restent sous le témoin nul, et l'inversion de signe entre les
deux jeux tient), mais ses traces portent désormais la même note que celles de la météo.

À l'inverse, deux choses sont **hors d'atteinte par construction**, et pas par chance : la
campagne génétique — son jeu de classement ne contient pas une occurrence de téléphérique —
et le **regard unique** du protocole : aucun des 23 découpages gelés n'offre d'option de
téléphérique pur dans son jeu de test.

**Ce que le correctif ne répare pas :** la sous-représentation de la marche. Elle passe de
11,309 % à 11,303 %, soit 0,006 point sur un écart de 14,7 points à l'enquête. Les
5 occurrences sont des *options proposées* ; une seule a reçu de la probabilité. Le défaut
était réel, sa contribution au biais est négligeable : l'instrument devient juste, le
diagnostic ne bouge pas.

### Les scores déjà en base ont été recalés, parce qu'une série est encore ouverte

Un score est **figé en base** au moment de l'évaluation, et une évaluation en cache le relit
tel quel. Rejouer les deux campagnes affichait donc les notes de l'ancien instrument, tandis
qu'un bras neuf aurait été noté par le nouveau : deux instruments dans le même tableau, ce que
le protocole interdit sur une série ouverte.

Les 18 scores concernés ont donc été recalculés depuis les décisions en cache — **sans un seul
appel LLM**, décisions intouchées, copie de sûreté de chaque base. `calibrate rescore
--from-decisions` ne pouvait pas le faire : il note toutes les évaluations contre les strates
d'un seul découpage, alors que chaque bras a le sien, et il ignore le jeu complet. D'où
`scripts/recalage_instrument.py`, qui lit le bras de chaque évaluation et **refuse** d'écrire
un score que ni l'ancien ni le nouvel instrument ne reproduit.

**Avant :** rejouer la campagne météo ou celle du contexte réaffichait les composites d'avant
le correctif.
**Après :** les deux campagnes sont notées par un seul instrument, et un second passage du
recalage ne signale rien.

---

## [2026-08-26] Le transport en commun couvre enfin toute l'année

La simulation ne pouvait tourner que du 16 mars au 12 mai 2026 : hors de cette fenêtre,
aucun bus, aucun métro, et pour tout signal un avertissement dans les logs. Elle couvre
désormais 2026 et 2027 en entier, pour Tisséo comme pour le TER.

**Avant :** 58 jours de calendrier. Un run lancé un 15 décembre ne planifiait aucune course
en transport en commun, sans erreur.
**Après :** 730 jours. Chaque journée porte soit l'offre réellement publiée par l'opérateur,
soit la copie verbatim d'une journée réelle de même signature — même jour de semaine, même
période du calendrier scolaire de la zone de Toulouse. Aucun horaire n'est synthétisé.

### Le feed en service sur-servait, et personne ne le savait

Les exports Tisséo sont glissants : chacun couvre ~35 jours mais n'est complet que sur les
premières semaines, après quoi l'opérateur ne publie plus que le métro. Fusionner deux
exports par simple union produit donc deux défauts, tous deux présents dans le feed qui
était en service :

- **13 250 trips le 08/04/2026**, là où ses deux sources en donnent 12 652 et 12 660 (+4,7 %) ;
  5 438 le 12/04 contre 4 646 et 4 886 (+11,3 %).
- La géométrie `14846` mélangeait **deux tracés différents** en un seul, entrelacés par une
  déduplication sur `(shape_id, shape_pt_sequence)` — un tracé chimère dont les distances ne
  correspondaient plus à ses arrêts.

Le nouveau pipeline retient **une seule source autoritaire par date** et rend la sur-offre
structurellement impossible.

La date de simulation du 16 mars n'était pas indemne non plus : ses 12 608 courses sont bien
les bonnes, mais **six d'entre elles portaient un tracé chimère** (la géométrie `14848`, 524
points en production contre 523 dans l'export d'origine). Le feed annuel restitue exactement
l'export : même nombre de courses, même empreinte d'offre.

### Ce que « période similaire la plus proche » veut dire

Les bornes des vacances scolaires de la zone C expliquent l'offre de très près : la chute du
20/04, le retour du 04/05, le vendredi de pont du 15/05 réduit à 10 877 trips. Une journée
sans donnée reçoit donc la journée réelle la plus proche **au sens des saisons** ayant le même
jour de semaine et la même classe de période.

Deux corrections que les données ont imposées : un **jour férié n'est pas un dimanche** (le
14/07 sert 5 674 trips contre 4 683 à 5 054 les dimanches de juillet), et les bornes de période
sont **apprises** plutôt que postulées — le samedi qui ouvre les vacances de printemps roule
encore en samedi scolaire, celui qui ouvre l'été non.

Le 1er mai reste sans service : les deux exports qui l'englobent l'omettent tous les deux.
L'extrapoler aurait inventé de l'offre un jour où le réseau ne roule pas.

### La preuve, pas la vraisemblance

On masque un mois réel, on laisse le pipeline le reconstruire, on compare : sur mai 2026
(30 journées, deux fériés, le pont de l'Ascension, deux week-ends), **l'écart maximal est de
5,3 % et la médiane sous 1 %**. Les jours ouvrés scolaires tombent sous 1,2 %.

Chaque journée du feed est tracée : d'où elle vient, à quel écart de saison, à quel niveau de
confiance. 97 journées de 2026 sont en confiance basse — essentiellement les vacances d'hiver,
de la Toussaint et de Noël, dont aucun export ne couvre l'équivalent 2026. C'est écrit, pas masqué.

### Testé

`make test-gtfs-year` : 41 tests unitaires sur feeds synthétiques, sans accès réseau, en moins
d'une seconde. Chacun porte sur une décision qui, prise à l'envers, donne un feed plausible
mais faux — la sur-offre par union, l'identifiant recyclé confondu avec la course d'origine,
la géométrie entrelacée, le creux d'un férié pris pour une troncature.

Les écrire a fait apparaître deux faiblesses, corrigées : la référence servant à détecter la
queue tronquée pouvait être **contaminée par cette queue même** (un export livré tardivement
passait intact), et deux courses de contenu identique le même jour étaient confondues sans
rien dire. Aucune des deux ne se manifeste sur les exports 2026 — les feeds produits sont
inchangés au bit près après correction — mais toutes deux passaient silencieusement.

### Rejouable à la prochaine livraison

```bash
make gtfs-year-dry      # ce qui deviendrait réel, ce qui resterait copié
make gtfs-year          # les quatre feeds + la trace de provenance
make gtfs-window START=2026-03-16 DAYS=64   # la tranche que consomme GAMA
```

Déposer de nouveaux exports suffit : les journées auparavant extrapolées qui deviennent
couvertes basculent d'elles-mêmes, et le manifeste le dit.

Les feeds sont produits **à côté** du jeu en service : ni `data/gtfs/` ni le graphe OTP ne
sont touchés. Les publier est une décision explicite, décrite dans `docs/arch/gtfs-annee.md`.

### Au passage

Le TER n'a jamais été dans le graphe OTP, contrairement à ce qu'affirmait la documentation
du routage — le graphe ne contient qu'un feed, et le mode `rail` n'est même pas demandé dans
les requêtes. C'est corrigé dans la doc, et le feed TER annuel est prêt le jour où on voudra
l'intégrer.

---

## [2026-08-26] Le prompt dit ce que les options ne disent pas — et rien de plus

Neuf changements sur le prompt soumis au modèle, dans un seul sens : ne servir que
l'information qui pèse sur la décision, et la servir là où elle pèse.

### Le bloc persona perd tout ce que les options portent déjà

La ligne `Mobilité :` disparaît. Elle annonçait la disponibilité de la voiture, l'abonnement
TC et la possession d'un vélo — or le jeu d'options dit déjà si la voiture ou le vélo est
prenable, et le canal narratif de la voiture avait été mesuré puis **rejeté** (+0,12 point de
part voiture, au niveau du bruit).

**Avant :** `Mobilité : ne conduit pas : se déplace en voiture uniquement en passager·ère,
conduit·e par un adulte du foyer — voiture toujours disponible | sans abonnement TC | possède
un vélo classique Contraintes : None`
**Après :** *(rien — ne reste que l'identité sociale)*

Cette phrase portait sur **384 décisions sur 1 810**, dont 330 de mineurs : un enfant de cinq
ans s'y voyait décrire comme passager d'une voiture toujours disponible. Quant à
`Contraintes : None`, c'était du texte mort — un littéral codé en dur, jamais implémenté,
constant sur 2 487 records sur 2 487.

### L'abonnement TC déménage sur l'option

Seule information de la ligne supprimée qui ne se déduit pas des options : une option bus
existe qu'on soit abonné ou non. Elle est donc conservée, mais accolée à l'option de
transport collectif — là où elle décide de quelque chose, et seulement quand un TC est
proposé.

**Après :** `- [0] foot,bus,foot: Temps de trajet : 1 h 36, dont 13 minutes de marche. Pas
d'abonnement aux transports en commun.`

### Une justification par option, plus une seule pour tout le persona

Le modèle rendait une phrase par persona. Il en rend désormais une **par option** : « une
phrase justifiant la probabilité de CETTE option par rapport aux autres ». On saura enfin
pourquoi la marche perd, option par option, au lieu de le demander dans la consigne.

Conséquence mesurée et anticipée : la sortie est cinq fois plus longue. Le plafond de
complétion passe de 4 096 à 8 192 tokens — à 5,39 options par persona et 2 825 tokens de
sortie moyens, l'ancien plafond aurait tronqué les lots en silence.

### La météo se lit toutes les trois heures, et annonce le vent et le verglas

La source portait **huit relevés**, le code n'en lisait que quatre. Un départ à 11 h recevait
la météo de 6 h, un départ à 17 h celle de 12 h — alors que le code météo diffère entre 12 h
et 15 h sur **159 jours sur 365**.

**Avant (départ 17 h) :** `Météo : 21°C, Partiellement nuageux.`
**Après (départ 17 h) :** `Météo : 25°C, Légères averses de pluie à proximité.`

Le bulletin gagne par ailleurs deux aléas, au franchissement d'un seuil seulement — rafales
au-delà de 30 km/h, risque de verglas sous 3 °C :

**Après :** `Météo : 2°C, Partiellement nuageux. Aujourd'hui 2°C à 11°C, lever 06:41,
coucher 19:18, rafales à 33 km/h, risque de verglas. Pas de précipitations prévues.`

Les deux viennent du bras d'agenda annoté rejeté en août, où ils décoraient chaque étape —
emplacement absurde pour le vent, qui est un maximum journalier et se répétait à l'identique
partout. Une journée ordinaire garde sa phrase mot pour mot, et un jeu gelé antérieur se
relit à l'identique : un test le verrouille.

L'anticipation « Météo plus tard » reste, elle, à quatre tranches. L'affiner en même temps
aurait refait l'erreur du bras rejeté : deux changements dans un même paquet, que la mesure
ne sait pas départager.

### La règle de chaîne dit enfin la vraie contrainte

**Avant :** « pense au stationnement et aux déplacements du reste de la journée, jusqu'au
retour au domicile » — ce qui se lisait comme une obligation de garder son véhicule toute la
journée.
**Après :** « chaque nouveau trajet doit obligatoirement repartir du lieu de stationnement
précédent […] même si certains trajets intermédiaires s'effectuent par d'autres moyens. »

La dernière clause est celle qui manquait : laisser la voiture au travail et aller déjeuner à
pied est un enchaînement valide.

### ⚠ Rien de tout ceci n'est encore crédité d'un gain

Neuf changements livrés ensemble ne sont attribuables à aucun. Et nos propres mesures
avertissent : le modèle réagit à la **mise en forme** du contexte plus qu'à son contenu — le
témoin nul de reformulation coûte 2,03 de composite, plus que le retrait de *tout* le
contexte. Retirer des segments et rendre une mention conditionnelle sont des changements de
mise en forme. Leur effet se mesurera contre ce plancher, pas contre zéro.

---

## [2026-08-26] Sur le jeu complet, retirer tout le contexte ne change rien

La mesure a été refaite sur l'union de `train` et `val` — **569 personnes, 1 568
déplacements**, soit 3,4 fois l'effectif de la première lecture, et sans un appel de plus
(les décisions déjà payées se relisent).

Retirer la **totalité** du contexte servi au modèle — équipement de mobilité, identité
sociale, météo, décomposition des étapes — déplace le composite de **0,27**. Réordonner et
réétiqueter ce même contexte, sans rien retirer, le déplace de **2,66**. Sur `train` seul,
l'ablation totale donne exactement **−0,00**.

Un épuisement de quota a obligé à rejouer une colonne sur une seconde clé, ce qui a produit
une mesure qu'on n'avait pas : **rejouer deux fois la même chose coûte 0,01**. Trois échelles
emboîtées, donc — 0,01 pour l'aléa de répétition, 0,27 pour tout le contenu du contexte,
2,66 pour sa seule mise en forme.

**Avant :** on supposait que la quantité de contexte servie au modèle déterminait la qualité
de la sortie, et qu'elle comptait davantage que le prompt.
**Après :** sur le plus grand effectif disponible, le contenu du contexte est indiscernable
du néant, et c'est la **forme** — l'ordre des lignes, les libellés — qui porte le seul signal
mesurable. Les parts modales, elles, bougent beaucoup : le composite est stable parce que les
écarts se compensent, pas parce que le modèle répond pareil.

---

## [2026-08-26] Le bulletin météo jugé sur le plus grand jeu disponible

Le bulletin météo enrichi — la seule des trois corrections du ticket 023 réellement livrée en
production — a enfin été mesuré **tel qu'il tourne** : tirage sur l'année entière, et rien que
la forme de la phrase qui change. L'A/B précédent le chiffrait par-dessus la fenêtre d'enquête,
une combinaison que la simulation ne joue pas.

**Résultat : aucun effet mesurable.** +0,19 de composite contre un plancher de bruit de −1,07,
soit un effet 5,6 fois plus petit que ce qu'un simple re-tirage de la météo produit tout seul.

### Ce qui change vraiment, c'est la finesse de l'instrument

La mesure porte sur un nouveau jeu de lecture, `all` — la réunion de `train` et `val`, soit
**1 810 décisions et 613 personas** au lieu des 516 décisions de `val` seul. `test` en reste
exclu : aucun regard neuf n'est consommé.

**Avant :** sur `val`, le bulletin valait +1,72 pour un plancher de ±1,98 — un rapport de 0,87.
Trop serré pour rien affirmer.
**Après :** sur `all`, il vaut +0,19 pour un plancher de 1,07 — un rapport de 0,18. Le
non-résultat devient un vrai résultat.

Le plancher a été divisé par 1,85 quand l'effectif a été multiplié par 3,5 : très exactement la
racine du rapport, comme du bruit de tirage. **L'instrument n'était pas cassé, il était trop
petit** — et c'est la troisième fois que le témoin nul change de signe selon le jeu (−0,34,
puis +1,98, puis −1,07), ce qui interdit de raisonner sur le signe d'un écart sous-liminaire.

### Le bulletin reste en production

Rien ne change à l'exécution : l'information qu'il porte — amplitude, soleil, créneaux
pluvieux — est factuellement absente du prompt sans lui, et ce choix de contenu est assumé.
Ce que la mesure ferme, c'est l'hypothèse qu'un gain de score se cachait dans sa forme.

### Deux campagnes en parallèle, sans se marcher dessus

Le jeton d'exclusion accepte désormais un **nom** (`PROTOCOL_LOCK_FILE`). Deux campagnes
peuvent tourner en même temps à une condition stricte : ne partager **aucun compteur de quota**
— ceux du free tier se comptent par modèle et par projet. Ici, une campagne du ticket 024
tenait le jeton par défaut sur un autre modèle-juge ; la mesure a pris le sien.

**Avant :** une seule campagne à la fois, même quand les quotas étaient indépendants.
**Après :** un jeton par seau de quota, chacun avec sa propre preuve d'exclusion archivée.

⚠ Le partage de compteur se **vérifie** (la clé de cache de l'autre campagne porte son
`prov=…|model=…`), il ne se suppose pas. Deux campagnes sur le même couple doivent partager
le jeton — un second jeton ne serait qu'une autorisation de se marcher dessus.

---

## [2026-08-26] Le modèle d'évaluation annoncé est enfin celui qui est appelé

La calibration déclarait un modèle d'évaluation, l'inscrivait dans sa clé de cache et dans
son store… et appelait l'API sans le préciser. L'adaptateur retombait donc sur le modèle par
défaut du fournisseur. Toute la discipline d'épinglage — y compris le garde-fou qui refuse un
alias flottant — portait sur une étiquette qui n'atteignait jamais l'API.

Le défaut ne se voyait que là où le modèle annoncé diffère du défaut du fournisseur, ce qui
est exactement le cas des configurations qui prennent soin d'épingler un nom stable.

**Avant :** une mesure pouvait être étiquetée `gemini-3.1-flash-lite` dans le store alors que
l'API avait servi `gemini-3.1-flash-lite-preview`. Deux modèles pouvaient se mélanger sous une
même clé de cache — précisément ce que le garde-fou prétendait empêcher.
**Après :** le modèle de la configuration est passé explicitement à chaque appel, et un test
échoue si un jour il cesse de l'être.

Conséquence à connaître : les mesures déjà publiées sous une configuration qui épingle un nom
stable sur un fournisseur dont le défaut est un alias — c'est le cas du jeu commun de la page
de synthèse — portent une étiquette de modèle qui n'est pas celle du modèle appelé. Les
chiffres restent valides et comparables entre eux (un seul modèle a servi) ; c'est leur nom
qui est faux.

---

## [2026-08-26] Le contexte pèse moins que sa mise en forme

Première mesure de l'échelle d'ablation du contexte : à prompt constant, retirer **tout** le
contexte servi au modèle — équipement de mobilité, identité sociale, météo, décomposition des
étapes — coûte **2,52** de composite. Réordonner et réétiqueter ce **même** contexte, sans
rien retirer, en coûte **2,03**.

Autrement dit la pente entière tient dans le plancher de bruit. Deux paliers dégradent même
*moins* qu'une simple reformulation, et la courbe sature dès le retrait de la météo : enlever
ensuite la décomposition des étapes, soit 55 % de la longueur du prompt, ne change plus rien
de mesurable.

**Avant :** « plus le contexte est riche, plus la sortie est juste » était une affirmation
sans chiffre, et le corollaire annoncé était que le contexte pèse davantage que le prompt.
**Après :** sur ce jeu, le contexte pèse 2,5 de composite et reste dans le bruit, quand le
prompt pesait 7,1 hors bruit. C'est l'inverse du discours prévu.

La confirmation sur `val` (165 personas) enfonce le clou et ajoute un fait que personne ne
cherchait : **les quatre ablations y améliorent le score** au lieu de le dégrader. Le signe
s'inverse d'un jeu à l'autre, et dans les deux cas l'amplitude reste sous celle du témoin nul.

Ce témoin nul est d'ailleurs, dans les deux jeux, la colonne **la plus dégradée** — plus que
le retrait de tout le contexte. Réordonner et réétiqueter l'information coûte plus cher que
la supprimer : le modèle réagit à la **mise en forme** du contexte plus qu'à son contenu.
C'est le seul point sur lequel les deux jeux concordent, ce qui le rend plus solide que la
pente elle-même — et ça ouvre un chantier, pas une conclusion : `L4n` cumule quatre
permutations et deux renommages, et on ne sait pas encore lequel porte l'effet.

À lire avec ses réserves : le regard sur le jeu de test est consommé, donc ces chiffres sont
exploratoires ; et le témoin nul réordonne sans paraphraser.

---

## [2026-08-25] Les courbes par strate ne traversent plus les tranches non couvertes

Sur les pages de synthèse (`detail_simulation.html`, `detail_progedo.html`, `index.html`),
les courbes de parts modales par âge et par distance traçaient tous les points, y compris
ceux assis sur un effectif sous le seuil de couverture (n < 5). La tranche « plus de 50 km »
du run de référence, portée par **une seule décision** — elle-même privée d'option voiture
par la chaîne des véhicules —, affichait ainsi « voiture 0 %, TC 60 % » : un lecteur en
concluait à un modèle cassé, alors que la tranche 20-50 km (n = 178) est la mieux ajustée
de toute la dimension (L1 5,7).

Le calcul connaissait déjà la couverture (`covered` dans `frames.py`) ; le rendu la
respecte désormais : la série observée est coupée aux tranches non couvertes (segments
séparés, pas de pont par-dessus), leurs points ne sont plus tracés, et le libellé de la
tranche est estompé. La référence enquête, assise sur ses propres effectifs, reste tracée
en entier.

**Avant :** la courbe voiture plongeait à 0 % sur « 50+ », tirée par 1 décision.
**Après :** la courbe s'arrête à 20-50 km ; le tick « 50+ » est grisé.

---

## [2026-08-25] La diversité des choix du modèle est chiffrée, sans dépenser un appel

« Le modèle manque de diversité » circulait sans chiffre. Il en a un désormais, et il tient :
sur le prompt de production, le modèle hésite en pratique entre **1,4 et 1,8 modes** sur les
3 à 4 qui lui sont offerts, et **un tiers à plus de la moitié** des personas reçoivent une
réponse *déterministe* (une probabilité ≥ 0,99 sur un seul mode). Douze évaluations déjà
payées ont suffi : tout se relit dans le store.

Trois livrables :

- **quatre métriques de dispersion** (entropie normalisée par l'offre, nombre effectif de
  modes, taux de réponses dégénérées à 0,90 et 0,99, variance inter-persona), volontairement
  **hors du composite** — les faire entrer dans la loss ferait chercher à la campagne une
  dispersion au lieu d'une justesse ;
- **`analyse_dispersion.py`**, qui tabule l'agrégat pondéré contre l'agrégat par vote
  majoritaire : leur écart *est* le coût du collapse (6,8 à 13,3 points selon le jeu) ;
- **`rewrite_context.py`**, qui produit les six paliers de l'échelle de contexte
  (`ctxL0`…`ctxL4`, plus le témoin nul `ctxL4n`) par retrait de texte, sans rejouer de
  simulation.

**Avant :** deux affirmations opposées sur le modèle — « il manque de diversité », « ce qui
compte c'est la quantité de contexte » — et aucun moyen d'en départager une. La part modale
agrégée pouvait tomber juste alors que le modèle rendait le même vecteur à tout le monde.
**Après :** la première est chiffrée et reproductible sur douze évaluations existantes ; la
seconde a son instrument prêt (six paliers gelés, témoin nul à +0,2 % de longueur), en
attente d'un budget d'appels.

Le protocole change aussi de forme : son §3 **ne nomme plus de modèle d'évaluation**. Un nom
se périme (dépréciation, quota épuisé, alias re-résolu) et faisait tomber l'instrument avec
lui. Ce qui est gelé est désormais la **constance du juge à l'intérieur d'une comparaison** :
deux chiffres ne se comparent que sous le même juge, le juge ne change pas tant qu'une série
est ouverte, et le régime effectif accompagne tout chiffre publié.

---

## [2026-08-25] Les tests du cache LLM repassent au vert

La suite `scripts/tests/test_llm_cache.py` couvre à nouveau le cache de décisions
LLM sans échec : le double de test des options expose désormais `mode_label()`,
que le cache appelle depuis l'étiquetage des modes par trajectoire (commit e04907c).

**Avant :** 2 tests sur 9 échouaient — le store levait une `AttributeError` avalée
en WARNING, rien n'était persisté, et les lookups attendus en hit rendaient `None`.
**Après :** 9 tests sur 9 passent ; le fake dérive son étiquette de mode de son code,
comme le fait `TravelPlan`.

---


## [2026-08-25] La mémoire des agents se coupe au lancement

Un run peut désormais se lancer sans la mémoire des agents — mémoire long terme ET
auto-réflexion — d'une seule option : `make run MEM=0` (et `MEM=1` pour la réactiver).
Sans réflexions à drainer, la fin de run est immédiate : plus de queue d'écritures LTM
à attendre avant `make down`.

**Avant :** couper la mémoire supposait d'éditer `GAMA/CityTransport/config/sim_params.yaml`
à la main — et l'injection de paramètres GAMA Server, qui semblait le canal naturel en mode
headless, était silencieusement écrasée par `load_sim_config` au premier cycle.
**Après :** `make run MEM=0|1` écrit le réglage dans `sim_params.yaml` avant le lancement,
et l'écho GAMA (`ltm=… self_reflect=…`) permet de vérifier ce qui a réellement été joué.

⚠ Le réglage est persistant (fichier réécrit à chaque run) : il vaut aussi pour les
runs IHM suivants tant qu'un `MEM=1` ne le rétablit pas.

---

## [2026-08-25] Le cinquième bras, ou comment un jeu de lecture fabrique un signal

Un cinquième bras a été mesuré : l'**agenda annoté par étape**. Chaque trajet prévu dans la
journée porte sa condition, sa température, sa luminosité — jour, nuit, aube, crépuscule — et
ses aléas : rafales au-delà de 30 km/h, verglas sous 3 °C.

**Avant :** `· 21:09 → home (≈37.5 km)`

**Après :** `· 21:09 → home (≈37.5 km) — ciel dégagé/ensoleillé, -2°C, de nuit, risque de verglas`

Un retour de nuit à −2 °C sur trente-sept kilomètres, que rien n'annonçait jusque-là. Au
passage, la source a livré une surprise : elle porte **huit relevés de trois heures**, et le
code n'en lisait que quatre depuis toujours. Le code météo diffère entre 12H et 15H sur
**44 % des jours** — deux trajets du même après-midi étaient donc annoncés identiques dans les
deux tiers des cas alors que la donnée savait les distinguer.

### Le résultat, et ce qu'il apprend

Sur le premier jeu de lecture, l'agenda annoté **dégrade le composite de 1,95 point** —
5,7 fois le plancher de bruit, le contraste le plus net de toute la campagne. La marche recule
de 13,3 % à 10,9 % alors qu'elle est déjà le mode le plus sous-représenté. On tenait un
résultat.

Sur le second jeu — le seul qui n'ait jamais servi à régler quoi que ce soit — le même
changement vaut **−0,17**. Il a changé de signe et s'est effondré au dixième du plancher.

**Il ne reste rien.** Rejet, comme pour la fenêtre et pour le bulletin.

### Le vrai enseignement porte sur l'instrument

Deux fois dans cette campagne, le jeu `screen` a produit un écart que le jeu indépendant n'a
pas confirmé. Ce n'est pas un hasard : il ne porte que 121 personas, et son plancher de bruit
y est **six fois plus étroit** que sur l'autre. Un plancher étroit fabrique des signaux.

**Avant :** un écart mesuré sur `screen` se lisait comme un résultat.
**Après :** `screen` ne se lit plus seul. Toute conclusion exige le jeu indépendant.

### Ce qui n'est pas condamné

L'agenda annoté n'est **pas porté en production** — il n'y a jamais été, et c'est exactement
ce qui a permis de ne rien livrer sur la foi du premier chiffre.

Mais la **résolution de trois heures** reste une piste ouverte. Elle voyageait dans le même
bras que l'annotation, la mesure ne peut pas les départager, et le rejet de l'ensemble ne la
condamne pas. Quatre relevés sur huit dorment encore dans la source.

### Un défaut trouvé par le garde-fou renforcé

Le contrôle qui vérifie que deux bras diffèrent ne comparait que la ligne météo. Or ce
cinquième bras ne se distingue du précédent que par le bloc de l'agenda : si l'annotation
n'avait rien annoté, **rien ne l'aurait signalé** et une évaluation aurait été payée pour un
écart nul par construction. Le contrôle porte désormais sur le prompt entier, et compare les
bras deux à deux au lieu de tous les comparer au premier.

### La page d'avancement montre enfin des chiffres

Deux graphiques, et jamais un seul. En haut, la **courbe des runs de production** — la seule
série de niveaux du dépôt, celle qui répond à « est-ce que ça s'améliore ». Elle n'est pas
monotone, et c'est un fait.

En dessous, **une barre par mesure**, groupée par unité et jamais sur un axe commun : un point
de composite et un point de part modale ne sont pas la même chose. Les mesures qui n'ont pas
été appliquées — cinq sur sept — sont estompées, pour qu'on ne lise pas un cumul qui n'a
jamais eu lieu.

Et chaque fiche porte désormais ses niveaux : `26,75 → 25,06 sur val`, plutôt qu'un écart nu.
Deux mesures affichent « composite non applicable » plutôt qu'un chiffre inventé.

---

## [2026-08-25] La fenêtre météo est rejetée — et c'est le bruit de l'instrument qui l'a tranché

L'A/B du ticket 023 a tourné : quatre bras, 232 appels, modèle d'éval épinglé. **Verdict :
rejet.** Ni la fenêtre d'enquête ni le bulletin enrichi ne produisent d'effet distinguable de
ce qu'un simple re-tirage produit tout seul.

Le résultat qui compte ne porte pas sur la météo, mais sur l'**instrument de mesure**.

Le témoin nul — un jeu qui rejoue le tirage sans changer **aucune** distribution — devait
donner le plancher de bruit. Il déplace le composite de −0,34 sur un jeu et de **+1,98** sur
l'autre. Il change de **signe**. Autrement dit : la variance propre de l'évaluation vaut
environ deux points de composite, et c'est plus que l'effet qu'on cherchait à mesurer.

| Contraste | `screen` | `val` |
|---|---:|---:|
| la fenêtre d'enquête — le traitement | −0,43 | −1,69 |
| **le témoin nul — le plancher de bruit** | **−0,34** | **+1,98** |
| le bulletin enrichi | +0,55 | +1,72 |

Sur `val` — le seul jeu réellement indépendant — le traitement est **sous** le plancher.

**Ce bras supplémentaire a coûté un quart de la campagne, et il a évité de publier un effet
qui n'existe pas.** Le témoin habituel du protocole compare les enregistrements que le
traitement n'a pas touchés ; ici il en touche 99 %, si bien que ce témoin aurait reposé sur
une vingtaine d'enregistrements et donné un plancher très étroit. Contre un tel plancher, le
−1,69 aurait été annoncé comme un signal sans hésitation.

**Une réserve, écrite plutôt que corrigée.** Sur `screen`, le script annonce « signal » parce
qu'il applique la règle du dépôt : le traitement dépasse le plancher. Mais 0,43 contre 0,34,
c'est 1,26 fois le bruit — un rapport qui ne veut rien dire. Le seuil n'a **pas** été modifié
après coup : déplacer les poteaux une fois le résultat connu invaliderait la mesure. La
sortie brute est archivée telle quelle, la réserve à côté, et un seuil opposable reste à
définir avant la prochaine campagne.

**Aucune conclusion sur la pluie**, comme le ticket l'exigeait *avant* la mesure — et il n'en
tire aucune.

**Ce qui change, et ce qui ne change pas.** Le tirage météo de production reste sur l'année
entière : la simulation doit pouvoir se jouer n'importe quand. La fenêtre d'enquête reste
disponible et gelée dans les manifestes des jeux `v10` et `v10b`, sans être adoptée nulle
part. Le **bulletin enrichi reste en production** — non parce que la mesure le soutient, mais
parce qu'elle ne montre pas qu'il dégrade, et que l'information qu'il porte est factuellement
absente du prompt sans lui. C'est un choix de contenu, pas un résultat, et il est assumé
comme tel.

Deux questions restent ouvertes, et le rejet ne les ferme pas : la variance d'un run de cinq
jours comparé à une moyenne de cent cinquante-deux, et l'excès de transports collectifs, à
20,8 % contre 12,4 % attendus.

**Avant :** un effet faible aurait été lu comme un effet.
**Après :** le plancher de bruit est mesuré à pleine masse, et il dit que l'instrument ne
sait pas trancher cette question-là.

---

## [2026-08-25] Le jeton d'exclusion, la fenêtre d'enquête et le bulletin météo

Trois livrables du ticket 023, tous en place **sans qu'un seul appel LLM ait été dépensé**.

### Plus aucune mesure ne peut tourner pendant un run

Une procédure du protocole exogène et une simulation consomment le **même quota LLM**.
Quand un fournisseur sature, la cascade bascule sur le suivant — et si la bascule survient
entre le premier et le second bras d'un A/B, les deux bras n'ont pas été évalués par le même
modèle. L'écart mesuré est alors confondu avec le traitement, et rien dans les agrégats ne le
montre.

**Avant :** rien n'empêchait de lancer `make run` au milieu d'un A/B. La seule protection
était de s'en souvenir.

**Après :** un jeton d'exclusion, pris et relâché explicitement.

```bash
make protocol-status
make protocol-lock SUBJECT="A/B fenêtre météo" CLOUD_PAUSED=1
make protocol-unlock
```

La prise refuse si un run tourne, ou si les services `controller` / `worker` sont en marche —
ils peuvent drainer une file de décisions même sans GAMA. Les scripts `ab_*.py` refusent
désormais de démarrer sans jeton ; seul `--dry-run` passe, puisqu'il ne dépense rien.

Un jeton dont le terminal a été fermé est **signalé, jamais levé automatiquement** : une
procédure peut encore tourner sous un autre shell, et un verrou qui se libère seul n'est pas
un verrou.

Deux instantanés de quota sont enregistrés, à la prise et au relâchement. Ils entrent dans
l'archive de la mesure : c'est la preuve qu'aucune consommation concurrente n'a eu lieu — et,
s'il y en a eu une malgré tout, le moyen de savoir que la mesure est à jeter.

⚠ **Le jeton est local et n'atteint pas la campagne génétique de la VM cloud.** C'est pour
cela que `CLOUD_PAUSED=1` est exigé : une vérification humaine, pas une garantie du verrou.
La limite est écrite dans la sortie du jeton, pas seulement dans la documentation.

### La météo des jeux gelés se tire enfin dans la fenêtre de sa cible

Les jeux de calibration tiraient un jour dans l'année climatique entière, alors que les
cibles auxquelles ils servent à comparer sont des déplacements recueillis du 20 septembre
2022 au 18 février 2023 — **152 jours, pas 365**. La fenêtre se lit maintenant dans le
référentiel de population et se gèle dans le manifeste du jeu.

Elle **franchit le 1er janvier**, ce qui est le piège de toute la manœuvre : écrite comme un
intervalle ordinaire, elle ne retiendrait aucun jour — et un tirage vide ressemble à un
tirage juste jusqu'à ce qu'on regarde les températures. Chaque jeu publie donc son contrôle
de validité : les profils de température et de précipitation des deux fenêtres, côte à côte.

### Le bulletin météo dit maintenant quand il pleut, et s'il fera nuit

**Avant :** `Météo : 2°C, Partiellement nuageux. Précipitations prévues dans la journée : 0,2 mm.`

**Après :** `Météo : 2°C, Partiellement nuageux. Aujourd'hui 2°C à 7°C, lever 07:55, coucher 17:25. Pluie prévue en soirée (0,2 mm sur la journée).`

Amplitude thermique, lever et coucher du soleil, créneaux où il pleut — trois choses qu'un
humain consulte avant de sortir un vélo, et qu'aucun agent ne voyait.

Il n'y a **pas** de « risque de pluie » en pourcentage, et il ne peut pas y en avoir : la
source météo ne porte aucune probabilité de précipitation. Un chiffre serait fabriqué. Seuls
les créneaux dont le code météo est effectivement précipitant sont annoncés.

Trois pièges de la source ont été chiffrés avant qu'une ligne de bulletin soit écrite.
25 jours sur 365 portent des millimètres sans qu'aucun créneau ne soit pluvieux : ils gardent
l'ancienne formulation, car **la forme enrichie ajoute et ne retranche jamais**. 30 créneaux
sur 1 460 sortent des bornes min/max de la source, jusqu'à 3 °C — les bornes annoncées sont
élargies aux créneaux réellement lus, faute de quoi le prompt se contredirait lui-même. Et la
neige n'apparaît qu'un seul jour dans l'année : la branche existe quand même.

### Quatre jeux, parce que trois ne suffiraient pas

`v10` porte la fenêtre, `v10b` la fenêtre et le bulletin, `v9n` **ne change rien du tout** —
même liste de jours, graine différente. Ce dernier est le plancher de bruit : le traitement
touche 99 % du jeu, si bien que le témoin habituel du protocole ne pèserait qu'une vingtaine
d'enregistrements et ne mesurerait plus rien. `v10` et `v10b` ne diffèrent que par la forme
de la phrase, à jour tiré identique : c'est ce qui rend les deux corrections séparables bien
qu'elles soient livrées ensemble.

L'A/B à quatre bras est chiffré : **92 appels sur `screen`, 140 sur `val`**, environ un quart
d'heure. Il n'a pas encore tourné.

⚠ **Aucune conclusion sur la pluie ne sortira de cette campagne**, quel que soit son
résultat. Le Δ mesuré change de signe selon le substrat — −1,20 pt sur `v7`, +1,10 pt sur
`v9` — pour un plancher de bruit de −1,16 pt. Un effet qui s'inverse quand on change de
substrat, à magnitude égale au bruit, est du bruit. La correction est thermique, et elle
seule.

---

## [2026-08-25] La fenêtre météo re-chiffrée sur le nouveau substrat, et un effet « pluie » qui s'effondre

La pré-mesure du ticket 023 — restreindre le tirage météo des jeux gelés à la fenêtre
d'enquête EMC² (152 jours) au lieu de l'année entière — a été **rejouée sur `v9`**, le
substrat issu du run de référence du 24 août. Zéro appel LLM dépensé : on ne compare que
des lignes de contexte.

L'effet thermique tient : **−4,74 °C** sur `v9`, −4,90 °C sur `v7`, contre +0,26 °C pour un
témoin nul qui ne fait que rejouer le tirage. C'est dix-huit fois le plancher de bruit.

Reste à savoir ce que « se réplique » veut dire au juste, et le recoupement a été fait plutôt
que supposé. Les deux substrats **partagent 89 % de leurs personas** — ce ne sont pas deux
échantillons indépendants de population, et il aurait été facile de l'écrire. Ce qui est
disjoint, c'est l'unité réellement mesurée : la clé de tirage météo, commune à 1,8 %
seulement. **99 % des enregistrements du nouveau substrat lisent une météo que la mesure
précédente n'avait jamais lue.** La réplication vaut donc pour la grandeur, pas pour la
population.

Au passage, la pré-mesure d'origine **comptait double** : ses 2 087 enregistrements
additionnaient `train`, `val`, `screen` et `rank` alors que les deux derniers sont des
sous-ensembles du premier — 519 lignes pesaient deux fois. Le décompte juste est 1 568. Le
défaut sur-pondère `train` sans renverser le résultat, mais il tenait depuis l'ouverture du
ticket, et la lecture ne prend désormais que `train` + `val`.

L'effet sur la pluie, lui, s'effondre — et c'est le résultat qui compte.

**Avant :** le ticket écartait toute conclusion sur la pluie par précaution, parce que le
Δ mesuré sur `v7` (−1,20 pt) était quatre fois plus petit que le bruit de re-tirage.

**Après :** le Δ **change de signe** selon le substrat — −1,20 pt sur `v7`, **+1,10 pt sur
`v9`** — pour un plancher de bruit de −1,16 pt. Un effet qui s'inverse quand on change de
substrat, à magnitude égale au bruit, est du bruit. Ce n'est plus une précaution de méthode,
c'est un résultat mesuré, et il est archivé comme tel.

Deux pièges ont été désamorcés au passage. Le jeu que le ticket prévoyait de nommer `v8`
**portait déjà** la réécriture `car_availability` du ticket 018 : comme la clé d'éval porte
le nom du jeu et non une empreinte de son contenu, la procédure serait tombée dans le piège
que le ticket lui-même documente — servir l'éval d'un tout autre jeu sans que rien ne le
détecte. Les jeux deviennent `v10` et `v9n`. Et la filiation se relit désormais sur le
manifeste de `v9`, qui est un jeu neuf tiré d'un run neuf, pas un dérivé de `v7`.

Le ticket 023 gagne enfin un troisième livrable : le **bulletin météo enrichi** — lever et
coucher du soleil, amplitude min/max de la journée, créneaux où il pleut.

**Avant :** `Météo : 2°C, Partiellement nuageux. Précipitations prévues dans la journée : 0,2 mm.`

**Après :** `Météo : 2°C, Partiellement nuageux. Aujourd'hui 2°C à 7°C, lever 07:55, coucher 17:25. Pluie prévue en soirée (0,2 mm sur la journée).`

Il n'y aura **pas** de « risque de pluie » en pourcentage : la source météo ne porte aucune
probabilité de précipitation, et un tel chiffre serait fabriqué. Seuls les créneaux dont le
code météo est effectivement précipitant sont annoncés.

Les contrôles de la source ont trouvé trois pièges, tous chiffrés avant qu'une ligne de
bulletin soit écrite : 25 jours sur 365 portent des millimètres sans qu'aucun créneau ne
soit pluvieux — le bulletin y garde donc l'ancienne formulation, car la forme enrichie doit
ajouter et jamais retrancher ; 30 créneaux sur 1 460 sortent des bornes min/max de la source,
jusqu'à 3 °C, ce qui aurait produit un prompt qui se contredit lui-même ; et la neige
n'apparaît qu'un seul jour dans l'année.

Le bulletin est livré dans la même campagne que la fenêtre, mais porté par un **quatrième
bras** d'A/B, pour que les deux corrections restent séparables malgré la livraison commune.

---

## [2026-08-25] Le run du 24 août devient la référence, et le substrat cesse de dériver en silence

Le run GAMA `2026-08-24_17_34` — celui qui rejoue en dur les corrections validées une à une
sur jeux gelés (temps terminal `tt3`, règle de chaîne au prompt système, anticipation de la
journée, mémoïsation des réflexions, disjoncteur du gateway LLM) — devient le **substrat
épinglé** de la synthèse. Il figure au journal des mesures comme la dernière version jouée,
avec sa trace archivée : composite **20,11 → 18,23**, le vélo redescendu de 16,1 à 13,3 %
(cible 4,1), la marche remontée de 10,2 à 11,9 % — donc le défaut de fond, la marche massivement
sous-représentée, **toujours pas corrigé**.

L'écart de −1,88 est mesuré, pas attribué : un run rejoue tous les changements à la fois, la
flotte de modèles a changé (96,4 % des décisions LLM sur les deux Gemini contre 77,9 %), et le
bruit de découpage vaut 5,41 points d'amplitude. La page le dit à l'endroit du chiffre.

**Avant :** épingler un nouveau run écartait la mesure du volet calibration, mais laissait
celle du volet modèle en place — la matrice comparait une simulation lue sur un run à un modèle
lu sur un autre, en les annonçant comme un seul substrat.
**Après :** le volet modèle est écarté aux mêmes conditions, sur le nom du run **et** sur
l'empreinte du journal — une reprise à chaud réécrit `moves.csv` sans changer de nom de run,
et seule l'empreinte distingue ces deux états. Écarté, il affiche l'action qui le rétablit.

Le journal des mesures se lit désormais dans l'ordre du temps, de la plus ancienne à la plus
récente. L'ordre était celui de la saisie dans le registre : une ligne écrite en tête y
remontait quelle que soit sa date, si bien qu'une page présentée comme une chronologie
racontait l'histoire dans le désordre. Il est maintenant calculé — et une date au mauvais
format est refusée, parce qu'elle trierait de travers sans rien dire.

Chaque ligne affiche aussi son **heure**, lue sur le document qu'elle met en avant, et c'est
elle qui départage les mesures d'un même jour — cinq tombaient le 24 août. L'heure inscrite
dans la page par son générateur est préférée à celle du fichier, parce qu'elle survit à un
clone ; sa provenance se lit en infobulle. Et quand le document lié ne tombe pas le jour de
la mesure, aucune heure n'est affichée plutôt qu'une heure qui ne situe rien.

**Avant :** `ticket 013 · 2026-08-24`, trois mesures du même jour dans l'ordre où elles
avaient été écrites.
**Après :** `ticket 013 · 2026-08-24 à 12:03`, et la journée se lit dans son ordre réel.

Les jeux gelés **`v9`** sont tirés de ce run (`test` : 258 personas, 723 décisions), et le
protocole gagne une règle : si un run GAMA plus récent que le substrat existe, **la question
est posée à l'expérimentateur** — rester sur le dernier jeu validé du journal des mesures, ou
reconstruire un jeu depuis le dernier run. Les deux ont un coût opposé, comparabilité contre
fidélité : ce n'est pas un arbitrage que l'outil doit rendre à votre place.

---

## [2026-08-24] Le bassin de tirage devient le périmètre d'enquête, pas un rectangle

La population synthétique se tirait dans un **rectangle** — l'emprise des arrêts Tisséo
élargie de 5 km — et se chargeait en écartant tout domicile qui en sortait. Ce rectangle ne
correspond à aucune définition d'enquête : mesuré, il ne contient que **221 des 453 communes**
du périmètre EMC² et **51 de ses 277 zones fines de 3ᵉ couronne**.

**Avant :** eqasim peuplait la Haute-Garonne entière, puis le chargement coupait au rectangle.
Résultat : 111 communes touchées sur 453, une 3ᵉ couronne à 54 personas pour 15,4 % du
cadrage, et 45 domiciles hors du périmètre d'enquête conservés dans la population de référence.
**Après :** le cadre de tirage est une **liste de communes** — celles du périmètre —, et le
filtre d'admission au chargement porte sur le **périmètre** et non sur le réseau TC. Un
habitant de 3ᵉ couronne à 60 km reste dans la simulation ; un domicile hors des 453 communes
en sort.

Deux réglages, `EQASIM_PERIMETER` et `EQASIM_DEPARTMENTS`, exposés dans `docker-compose.yml`,
dans l'API de génération et dans la cellule « Paramètres » du notebook. Le cadre **prime sur
la bbox** — un rectangle ne sait pas dire « ni plus ni moins » — et il **échoue** s'il est
vide : sans ce garde-fou, une faute de frappe ferait peupler tout le département en silence.

⚠ **Limite assumée, chiffrée et publiée.** Cette livraison ne sert que la **Haute-Garonne** :
346 des 453 communes. Les 107 autres — Gers, Tarn, Tarn-et-Garonne, Ariège, Aude, dont **100
en 3ᵉ couronne** — demandent +10 Go de données d'adresses et de bâti. Conséquence : la 3ᵉ
couronne plafonne à **10,6 %** de la population quand l'enquête en compte **15,4 %**, soit un
résidu **structurel** de 4,7 points. En écart global de répartition : 11,7 → ≈ 9,5 points, là
où le périmètre complet donnerait ≈ 2,7. La limite est inscrite dans les « limites à publier »
de la documentation, sous le n°6.

**Une population non enrichie ne passe plus en silence** : si le trait `residence_zone`
manque, le chargement retombe sur l'ancien filtre **et lève une alarme**. Sans elle, on
croirait filtrer sur l'enquête alors qu'on filtre sur le réseau de transport.

**Correction d'une affirmation antérieure** : la documentation annonçait que les activités
hors du graphe OTP étaient « snappées sur le bord » et que `identity.home` portait des
coordonnées post-snap. C'est faux — la fonction de snap existe mais **n'est appelée nulle
part**. Aucun domicile n'a jamais été déplacé. Ce qui reste vrai, et qui est désormais écrit :
rien ne ramène dans le graphe une activité qui en sort, donc les personas éloignés n'auront
pas d'offre en transport collectif tant que le graphe restera celui de l'agglomération.

Reste à faire, et c'est de la machine : régénérer la population avec ce cadre. La procédure
est dans `docs/setup/population.md`.

---

## [2026-08-24] Ce que la correction des couronnes coûte au score : +2,11 points

`make couronne-v7` chiffre l'effet du reclassement des couronnes de résidence, **sans un seul
appel LLM** : les décisions du jeu gelé `v7` sont déjà en base, et la couronne n'entre ni dans
le prompt du persona ni dans la clé du cache de décisions. Seule l'agrégation change, donc
« à décisions constantes » est structurel et non une précaution.

**Avant :** le stratum 3ᵉ couronne était **vide** sur cette population, et Toulouse portait
la masse de 47 agents qui habitent en réalité la 1ʳᵉ couronne. L1 par zone : 41,26 pt.
**Après :** quatre strates peuplées, et 43,38 pt. Les quatre se dégradent — Toulouse +0,90,
1ʳᵉ +4,27, 2ᵉ +1,68 — et la 3ᵉ apparaît à 41,88.

C'est l'issue attendue : le ticket retire un avantage que la mesure n'avait pas mérité. La
page « Avancement et résultats » porte la ligne, avec la précision que ce n'est **pas** un
composite : `lieu_residence` n'est pas une dimension notée, le composite comparable ne bouge
pas d'un millième, et publier ce zéro serait prendre l'absence de mesure pour une mesure.

**Le piège qui a failli faire publier l'inverse.** La première version de la mesure pondérait
le L1 par la masse observée de chaque strate. Elle rendait **−0,26 pt** — une amélioration —
alors que chaque strate se dégradait. Explication : le reclassement sort des agents de
Toulouse, la strate la pire, et la moyenne baisse par changement de mélange. Comparer deux
*classements* avec des poids qui se déplacent en même temps que les strates n'est pas une
règle de score valide. Les poids publiés sont ceux du cadrage de population, identiques des
deux côtés. Sans le principe « une correction qui améliore le score est suspect », ce
résultat serait parti en publication.

**Une masse exclue est désormais visible.** Les pages de synthèse affichent une ligne
« — hors référentiel — » par dimension : elle porte la masse des catégories que la référence
EMC² ne ventile pas — `hors périmètre` pour la zone, « Autres » pour le type de logement, qui
était dans ce cas depuis des mois sans que rien ne le montre. Exclu des cibles ne veut pas
dire inexistant.

Enfin, les générations neuves poseront le trait elles-mêmes : le pipeline eqasim écrit la
couronne et la commune juste après le recalage des localisations sur le réseau. ⚠ Ce dernier
point est **écrit mais non rejoué** — il demande une reconstruction du service et une
régénération complète ; d'ici là, une population neuve doit passer par `make residence-zone`.

---

## [2026-08-24] Le journal ne devine plus la couronne d'un agent, il la lit

La colonne « Lieu de résidence » de `moves.csv` recopie désormais le trait du persona. Elle
ne consulte plus la distance du domicile à l'hypercentre — et le module qui l'écrit
**n'importe même plus** la fonction qui la calculait.

**Avant :** à chaque déplacement journalisé, la couronne était recalculée par un disque de
8 km autour du Capitole. Un agent de Blagnac était journalisé « Toulouse », puis comparé à
une cible voiture de 31 % au lieu de 64 %.
**Après :** la colonne porte la couronne de la **commune** du domicile, et accepte
`hors périmètre` pour les domiciles situés hors des 453 communes de l'enquête — une valeur
de première classe, dont la masse sera comptée au lieu d'être diluée en 3ᵉ couronne.

Une population enrichie avant ce correctif produit une colonne **vide**, jamais une couronne
devinée. Vide n'est pas une modalité : c'est une information, et elle est visible.

Le retrait de l'import n'est pas cosmétique. Tant qu'il existait, un « repli raisonnable sur
la distance » pouvait être rétabli en une ligne à la première relecture distraite, et il
aurait reproduit l'écart en silence. Un test l'interdit maintenant explicitement.

Le classement métrique, lui, survit — pour le **temps terminal** seul, dont les lois d'accès
et de stationnement ont été estimées avec lui. Son docstring dit désormais ce qu'il est,
cesse de prétendre porter la définition EMC² de la résidence, chiffre la divergence assumée
avec le journal (34 s par bout de trajet sur le pire couple observé) et dit ce que coûterait
son alignement : un ré-export de la loi de temps terminal, donc trois caches invalidés et un
run complet. Un autre ticket.

Deux tests existants exigeaient l'inverse de tout ça — que les deux classements
coïncident. Ils sont inversés, et leur inversion **est** la décision.

---

## [2026-08-24] Les personas savent dans quelle commune ils habitent

`make residence-zone` pose sur chaque persona la couronne de son domicile **et sa commune**,
au découpage de l'enquête EMC² — plus par sa distance au Capitole. Le trait est ajouté en
tête des enrichissements du notebook de génération, et il est le seul de l'étape à être
**observé** : ni tirage, ni loi, ni sel. Un domicile est dans une commune ou il n'y est pas.

**Avant :** la couronne d'un persona était recalculée à chaque écriture du journal, par un
disque de 8 km autour du Capitole. 249 des 1 021 personas de la population de référence
étaient ainsi comparés à la cible d'une autre zone, dont 66 « Toulousains » habitant en
réalité Blagnac, Balma ou Colomiers.
**Après :** la couronne et la commune sont écrites dans le persona, lues dans le référentiel
de l'enquête. Le journal n'aura plus qu'à les recopier (lot suivant).

**Trois valeurs, trois significations** — la distinction est le cœur du correctif : une
couronne quand le domicile est dans le périmètre ; `hors périmètre` quand il est connu et
**dehors**, ce qui n'est pas une couronne et n'a aucune cible ; **aucun trait** quand le
persona n'a pas de coordonnées, parce qu'affirmer « dehors » de quelqu'un dont on ne sait
rien serait pire que de ne rien dire. La commune, elle, ne s'invente jamais.

La validation ne porte pas sur une distribution mais sur un **accord** : la couronne écrite
par le code de zone fine est recalculée par appartenance géométrique aux polygones de
couronnes, et les deux doivent coïncider à 100 % sur chaque population. L'écart au cadrage
de population, lui, a son propre code de sortie : il mesure la concentration spatiale du
tirage — un autre sujet — et le confondre avec un échec apprendrait à ignorer les échecs.

Au passage, la passe recoupe le ticket 020 par un chemin indépendant : 24,4 % de personas
reclassés sur la population de référence, 19,1 % sur celle des jeux gelés. Les chiffres
publiés tiennent.

⚠ Une population épinglée par un manifeste de jeu gelé ne s'enrichit **jamais en place** :
`make residence-zone POP=… OUT=…` écrit ailleurs. Quatre jeux (`v5` à `v8`) épinglent le
même fichier par son sha256.

---

## [2026-08-24] Deux affirmations sur le modèle passent au statut de mesure (ticket 024)

Deux choses se disaient du modèle sans qu'aucun chiffre ne les soutienne : *il manque de
diversité, il répond toujours la même chose* et *plus on lui donne de contexte, plus il est
juste*. Le [ticket 024](tickets/ticket_024_diversite_et_contexte.md) les cadre en mesures
opposables, toutes lues contre la **dernière version de prompt acceptée**. Il ne corrige
rien : il produit des chiffres, les archive, et ouvre une porte de décision.

**La moitié du travail était déjà faite et personne ne l'avait présentée comme telle.** La
part voiture produite par le champion est **plate — 42,7 % à 49,1 % selon la distance —
quand la réelle va de 18 % à 77 %**. Le déficit de marche (−14,5 points) n'est donc pas un
biais uniforme : c'est la somme d'un effondrement sur les trajets courts (−44,7 points en
dessous d'un kilomètre) et d'un excédent sur les longs, qui se compensent en partie.
L'agrégat masquait le défaut au lieu de le montrer.

**Ce qui coûte zéro appel LLM et n'avait jamais été lu.** Les décisions par persona
dorment déjà dans le store. Comparer l'agrégat pondéré à l'agrégat par vote majoritaire ne
demande donc aucune dépense — et cet écart *est* le coût du figement. Même chose pour
quatre grandeurs de dispersion (entropie normalisée, nombre effectif de modes, taux de
réponses quasi certaines, variance entre personas) qui n'existaient nulle part.

**Le chiffre qui décide du discours n'était dans aucune des deux affirmations.** Dire « le
prompt joue mais le contexte compte davantage » est une comparaison d'amplitudes. Celle du
prompt est connue : **−7,13 de composite**, IC90 [−10,37 ; −4,35]. Celle du contexte est à
mesurer, par retrait progressif d'information dans un jeu gelé. Si elle ne dépasse pas
7,13, c'est l'inverse qu'il faudra dire.

**Un piège attrapé avant d'avoir dépensé.** La température d'évaluation est gelée à zéro.
Un bras « choix direct » y rend une réponse unique par persona : sa dispersion vaut zéro
**par construction de l'instrument**, pas par propriété du modèle. Le comparer aux
distributions actuelles sur ce terrain n'aurait rien mesuré, et rien ne l'aurait signalé —
le même motif que « l'absence de donnée n'est pas une donnée ». La comparaison se lit donc
au niveau agrégé, et la limite est écrite dans le ticket plutôt que découverte après coup.

Le ticket note aussi sa propre dépendance : le jeton d'exclusion qu'exige le protocole
n'est pas encore livré ([ticket 023](tickets/ticket_023_fenetre_meteo_jeux_geles.md), lot
1). Les deux premiers lots ne consommant aucun quota, ils peuvent partir sans lui — les
suivants, non.

---

## [2026-08-24] La couronne d'un domicile se lit dans le code de sa zone fine

`make communes-couronnes` publie une ressource de plus, `llm_module/data/zf_couronne.json` :
les 785 zones fines de l'enquête avec leur secteur de tirage, leur couronne, leur code INSEE
et **leur commune**. Un domicile déjà résolu en zone fine — ce que la simulation fait pour
le type de logement et l'équipement vélo — donne donc sa couronne sans aucune géométrie, et
la commune vient avec.

**Avant :** la couronne d'un domicile se déduisait de sa **distance au Capitole** (moins de
8 km = Toulouse), et rien dans le dépôt ne portait la correspondance zone fine → couronne.
**Après :** la couronne est **lue** dans le référentiel de l'enquête, et la commune du
domicile est disponible à côté d'elle — c'est ce qui rendra le classement auditable plutôt
que seulement correct.

Le grain est la zone fine, pas le secteur : une table `secteur → couronne` de 88 lignes
aurait donné la couronne mais jamais la commune. La classification de référence par
appartenance géométrique, qui vivait dans l'audit du ticket 020, est montée dans
`llm_module/core/residence_zone.py` : l'audit et la production lisent maintenant la même,
parce que deux copies d'une définition finissent par diverger.

Verrous ajoutés : l'export refuse un secteur sans zone fine (les deux couches SIG doivent
décrire le même périmètre) ; le lecteur refuse une ressource d'une autre version, une
modalité hors des quatre couronnes, un secteur rattaché à deux couronnes ; la commune ne se
déduit **jamais** d'un secteur, qui couvre plusieurs communes. Et l'équivalence entre le
classement par code et le classement géométrique n'est plus une mesure ponctuelle : elle est
rejouée à chaque exécution des tests, sur les 785 zones.

---

## [2026-08-24] Les couronnes de résidence : deux équivalences mesurées avant de corriger

`make audit-couronnes` répond à une question qui bloquait la correction des couronnes de
résidence (ticket 021) : peut-on lire la couronne d'un domicile dans le **code de sa zone
fine**, au lieu de la deviner à sa distance au Capitole ? La réponse était supposée ; elle
est maintenant mesurée, sur sept portes, dont un recoupement par un chemin indépendant.

**Avant :** le ticket affirmait un accord de 100 % entre le classement par code de zone et le
classement par appartenance géométrique. Rien dans le dépôt ne l'établissait — ce qui était
vérifié, c'était l'intégrité de la jointure zone fine → secteur, pas l'accord de deux
classements sur des domiciles.
**Après :** 785 / 785 au grain zone fine, 1 021 / 1 021 au grain domicile, et « hors de la
couche de zones fines » désigne **exactement** les mêmes 45 domiciles que « hors des quatre
couronnes ». La commune, elle aussi, se reproduit depuis le code de zone : c'est ce qui
permettra de publier la commune du domicile à côté de sa couronne, et donc de rendre le
classement auditable.

La cible ne modifie rien et refuse de se taire : code de sortie `2` si une porte échoue,
`3` si une porte est **non mesurable** faute des données d'enquête d'accès restreint — parce
qu'une porte non mesurée est une porte qui passe. Trace :
`docs/traces/2026-08-24_couronne_equivalences/`.

---

## [2026-08-24] Un journal des mesures : « avancement et résultats »

Nouvelle page, `make avancement` → [`docs/synthesis/avancement_et_resultats.html`]. Elle
répond à une question que les pages existantes ne posaient pas : **qu'est-ce qu'on a
essayé, et qu'est-ce que ça a rendu ?** Une ligne par correction testée — base de
référence, base modifiée, modification faite, résultat obtenu, score, commentaire.

La distinction avec `index.html` est le point : celle-ci score un **run** de simulation, le
journal recense les **mesures sur jeux gelés**, qui coûtent des dizaines d'appels LLM au
lieu d'heures de calcul. Les mêler sous un même chiffre ferait perdre le seul repère qui
compte — de quoi le score parle. Chaque ligne renvoie donc à sa trace archivée **et** à la
synthèse intermédiaire correspondante quand elle existe.

Quatre mesures y figurent, toutes du 2026-08-24 :

| Mesure | Score | Verdict |
|---|---|---|
| Temps terminal voiture (`v5` → `v6`) | −4,52 composite | mesuré, périmètre partiel |
| Temps terminal voiture + vélo (`v5` → `v7`, = production `tt3`) | −2,17 composite | **adopté** |
| Puce « Chaîne de la journée » au prompt | +0,21 composite | rejeté |
| `car_availability` réalignée (`v7` → `v8`) | +0,12 pt de part voiture | rejeté |

**Le registre n'est pas un plan.** Une ligne n'existe que si la mesure a été faite —
sinon la page devient une liste d'intentions et cesse de dire ce qui est établi. Et le
rendu **refuse d'écrire**, code de sortie 1, si une trace citée n'existe pas sur le disque,
si un champ manque ou si un verdict sort du vocabulaire : une page de résultats qui se
dégrade en silence est pire qu'une page absente.

**Un écart de chiffre à arbitrer.** Le ticket 013 et le changelog citent **−5,28 de
composite** pour la correction du temps terminal. L'archive committée
(`docs/traces/2026-08-24_temps_terminal/results.json`) ne contient que quatre composites,
et le delta `v5` → `v6` y vaut **−4,52** (27,00 → 22,48), le delta `v5` → `v7` **−2,17**.
Le 5,28 n'est pas reproductible depuis la trace : la page publie les chiffres vérifiables
et l'écart reste à trancher.

---

## [2026-08-24] Le partage de la voiture testé sans payer de run : rejet du canal narratif

Le ticket 018 a été mesuré selon
[`protocole-parametre-exogene.md`](arch/protocole-parametre-exogene.md) — la méthode qui
chiffre une correction sur des jeux gelés **avant** de dépenser des heures de simulation.
Coût total : 227 appels LLM, aucun run.

**Le résultat.** Réaligner `car_availability` sur EMC² — 72 personas sur 818 basculés de
« voiture à partager dans le foyer » à « voiture toujours disponible », ce qui porte la
distribution de 60,9 / 25,6 / 13,6 % à 69,7 / 16,7 / 13,6 % pour une cible de
70,0 / 16,9 / 13,1 % — ne déplace **pas** les parts modales de façon détectable. Sur les
45 personas traités des deux jeux disjoints, l'effet voiture vaut +1,34 pt pour un plancher
de bruit de 1,31, soit exactement le niveau du bruit.

**Et c'est l'amplitude qui ferme la question, pas le test.** En prenant le point estimé au
pied de la lettre, l'effet **agrégé** vaut **+0,12 pt de part voiture** — contre les 5,28 de
composite que la même méthode avait rapportés sur le temps terminal. Le biais de niveau est
réel (+8,7 pts de personas en `some`), mais le faire passer par le narratif du persona ne
coûte pas un dixième de point.

**Ce que le rejet ne couvre pas**, et qui reste ouvert : la **rivalité**. Un jeu gelé ne
rejoue ni l'offre d'options ni les chaînes de véhicule, donc les 6,1 % de trajets voiture
qui partent alors que toutes les voitures du foyer sont déjà dehors ne sont pas testables
ainsi. La sortie recommandée du ticket devient l'**option C** — écrire la limite et la
publier — le ticket 017 continuant de corriger le niveau gratuitement.

**Une cible recalculée plutôt que reprise.** `make car-availability` mesure la distribution
depuis les microdonnées avec la règle de dérivation d'eqasim, et refuse de publier si son
contrôle positif échoue. Il donne 70,0 / 16,9 / 13,1 % là où le ticket citait
69,5 / 16,9 / 13,6 — le recoupement tient. Contrôle négatif au passage : la non-réponse du
permis est **nulle** chez les majeurs, donc la variable n'est pas morte.

**Before :** « `car_availability` pèse −7,3 pt de voiture (politique logit), et la
population synthétique en voit 6,9 pts de trop » — un biais réel, d'effet supposé.
**After :** le même biais, chiffré à **+0,12 pt de part voiture** dans la simulation. Le
LLM, sous le prompt de production, est bien moins sensible à cette phrase que ne l'est la
politique logit à la variable correspondante.

---

## [2026-08-24] Un faux positif attrapé, et le protocole de mesure renforcé

Le premier chiffre du test ci-dessus annonçait **+7,27 pt de voiture** — une amplitude qui
recoupait presque exactement l'effet marginal connu de la politique logit. Tout concordait.
C'était faux, et l'autopsie a produit quatre règles nouvelles, désormais dans le protocole.

**Le témoin placebo, gratuit et décisif.** Quand une correction ne touche que 9 % des
records, les 91 % restants sont identiques dans les deux bras — mais ré-évalués dans chacun,
donc porteurs de bruit et d'aucun signal. Ils forment un **témoin placebo qui était déjà
payé** : leur Δ devrait valoir zéro, et ce qu'on y lit est le plancher de bruit de
l'instrument. Sur le premier jeu, la lecture agrégée donnait −0,29 pt de voiture, soit le
**signe inverse** de l'effet traité : −1,12 × 0,901 de bruit contre +7,27 × 0,099 de signal.
Sans ce témoin, un chiffre de signe faux partait au changelog.

**Le plancher doit être ramené à la masse traitée.** Comparer un Δ mesuré sur 22 unités de
masse à un plancher mesuré sur 201 est un faux test. En 1/√n, le plancher passe de 1,58 à
4,79 pt. Le cas qui trompe le plus est celui du jeu `val` : **au-dessus du plancher brut,
sous le plancher mis à l'échelle**.

**La dispersion avant la moyenne.** Derrière les +7,27 pt, une médiane de +1,3 pt : 5
personas en hausse, 1 en baisse, 3 immobiles, et deux cas passant de 70 % à 100 % portant
tout le résultat.

**Vérifier la filiation des jeux avant de parler de réplication.** Le manifeste dit
`rank ⊂ screen ⊂ train`. Il n'y a jamais eu deux mesures en désaccord — il y a eu une
sous-population de 9 personas qui fluctuait à l'intérieur des 35. Seuls des jeux **disjoints**
se mettent en commun.

**Outillage.** `prompt_calibration/ab_car_availability.py` publie les trois lectures
(traité / placebo / agrégat) et refuse un jeu où rien ne diffère ;
`rewrite_car_availability.py` produit le jeu dérivé ; `archive_car_availability.py` écrit la
trace committée. Deux défauts corrigés en passant : la réécriture perdait l'espace avant le
séparateur `|` — elle changeait donc la *structure* du rendu en plus de la variable — et les
manifestes hérités annonçaient `version: v5` dans un répertoire `v8`.

---

## [2026-08-24] Un quart des habitants simulés étaient notés sur le territoire du voisin

La simulation note ses résultats en les comparant à une enquête de terrain. Personne
n'avait vérifié que les deux comptaient la même population. Les neuf écarts de base sont
désormais mesurés, chacun avec un chiffre et un verdict — deux à corriger, cinq à publier
comme limites, deux conformes, **aucun laissé sans mesure**.

Le plus lourd n'a rien à voir avec les décisions des habitants : c'est de la géographie.
L'enquête découpe ses couronnes par **liste de communes** (1 / 69 / 108 / 275) ; le code
classait par **distance à l'hypercentre** (8 / 20 / 40 km), en annonçant en commentaire
qu'il s'agissait des mêmes modalités.

**Before :** le disque de 8 km compte 442 « Toulousains », dont 66 habitent en réalité
Blagnac, Balma, Tournefeuille, Colomiers ou Ramonville — comparés à une cible voiture de
31 % au lieu de 64 %
**After :** l'écart est mesuré, nommé commune par commune, et archivé : **249 personas sur
1 021 (24,4 %) changent de couronne**

L'erreur ne va que dans un sens — les 179 zones fines de Toulouse tiennent toutes dans
7,0 km, donc elle gonfle Toulouse et vide la 1ʳᵉ couronne. Et elle **flatte la note** :
l'écart aux cibles par zone vaut 47,8 points sous le classement publié contre 50,7 sous le
classement correct, sur le même run et les mêmes décisions. Le stratum « 3ᵉ couronne »,
absent du tableau publié, réapparaît avec 99 trajets.

**Le contre-exemple, aussi instructif.** La taille de ménage affichait 2,71 contre une
cible de 2,08 — un écart de 30 % qui n'existe pas. Une population synthétique échantillonne
des *personnes* : un ménage de cinq y apparaît cinq fois. En rendant à chaque ménage un
poids de 1, on obtient 2,01, et 1,23 voiture par ménage pour une cible de 1,25. Une base de
comparaison non déclarée fabrique aussi des défauts imaginaires.

**Trois autres écarts découverts en chemin :**

- **45 habitants (4,4 %) vivent hors des 453 communes enquêtées**, jusqu'à 114 km du
  Capitole. Le classement les rangeait en « 3ᵉ couronne », où ils formaient 76 % du
  stratum. « Hors périmètre » n'est pas une couronne : c'est maintenant une modalité à part.
- **Aucun trajet des vingt derniers runs ne s'est joué sous la pluie**, contre 44,7 % de
  jours pluvieux dans la fenêtre d'enquête — et c'est le vélo, mode le plus sensible à la
  météo, qui arbitre les décisions de ce projet depuis deux tickets. La cause exacte est
  précisée plus bas : ce n'est pas une affaire de saison.
- **La hiérarchie de mode principal est inversée** : l'enquête compte un trajet
  voiture + métro comme un déplacement en transports collectifs (760 fois sur 770), le code
  le compterait en voiture. Sans effet aujourd'hui — aucun itinéraire simulé ne mêle les
  deux modes — mais une part de la cible « transports collectifs » est de ce fait hors
  d'atteinte. **Remesurée depuis par strate, elle est bien plus lourde que son chiffre
  global de 1,4 point** : voir plus bas.

Le soupçon de départ, en revanche, est levé : la marche d'accès à un bus ou à une voiture
n'est comptée comme un déplacement ni côté simulation ni côté enquête. La marche n'était pas
surestimée par construction.

**Le cadrage de l'enquête n'est plus décoratif.** Le fichier qui décrit la population
interrogée existait, mais aucun code ne le lisait et l'essentiel dormait en commentaire. Il
est maintenant chargé par un module qui refuse un cadrage incohérent, couvert par 17 tests,
et **chacune de ses valeurs a été recalculée depuis les données brutes de l'enquête** —
indépendamment de la publication d'où elle avait été recopiée. Deux valeurs en sont sorties
corrigées : 54 585 déplacements recensés et non 54 785, et 69 / 108 communes en première et
deuxième couronne et non 68 / 109 (même total de 453).

**Nouveaux outils :**

| Commande | Ce qu'elle fait |
|---|---|
| `make communes-couronnes` | Extrait la correspondance commune → couronne des 453 communes, et la géométrie des couronnes — la donnée qui manquait |
| `make audit-perimetre` | Rejoue les neuf mesures sur une population et un run. Sort 0 si tout est conforme, 2 s'il reste un écart à corriger, **3 si un axe n'a pas pu être mesuré** |

Le code 3 n'est pas un détail : dans ce projet, l'absence de mesure produit régulièrement
la note parfaite. Un axe silencieux est un axe qui passe.

Rapport lisible, traces et tables : `docs/traces/2026-08-24_perimetre_population/`.
Détail technique : `docs/arch/perimetre-population.md`.

**La correction des deux écarts « à corriger » est cadrée** (ticket 021) et prend une voie
qui ne coûte aucun run : la couronne sera **posée sur l'habitant** à la génération, au lieu
d'être devinée à sa distance du centre au moment de la simulation. Les deux écarts vivent en
effet dans la colonne du journal, c'est-à-dire sur le seul chemin qui ne porte aucun cache —
les corriger là n'invalide rien et ne demande pas de rejouer une simulation.

La donnée nécessaire est déjà dans le conteneur : le code de zone fine que la simulation
résout déjà pour chaque domicile porte, sur ses trois premiers chiffres, le secteur
d'enquête — et le secteur porte la couronne. Vérifié sur les 1 021 habitants : **accord de
100 %** avec le classement géométrique. Il ne reste qu'une table de 88 lignes à publier. Le
« hors périmètre » vient gratuitement, puisque le résolveur rend déjà « aucune zone » pour
ces 45 domiciles.

Attendu de cette correction : **le score se dégrade**, de 47,8 à 50,7 points d'écart aux
cibles. C'est le critère de réussite et non un échec — elle retire un avantage que la mesure
n'avait pas mérité.

**Correction sur l'écart de météo : la cause n'est pas la saison.** Question posée après
coup : l'enquête porte-t-elle sur ses cinq mois de collecte, ou interroge-t-elle les gens
sur leurs habitudes annuelles ? Elle porte sur ces cinq mois — la méthode recueille les
*déplacements de la veille*, et les dates de référence des données brutes ne couvrent que
septembre-décembre 2022 et janvier-février 2023, jours ouvrés seulement.

**Mais l'enquête ne publie pas « un jour d'automne » : elle publie « un jour moyen de
semaine ».** La fenêtre automne-hiver est la méthode pour obtenir une journée ordinaire, pas
une revendication sur la saison. Le diagnostic change donc de nature, et deux affirmations du
rapport initial étaient trop sévères :

**Before :** « une cible d'automne, une simulation de printemps »
**After :** « une moyenne de 152 jours comparée à une réalisation de 5 jours » — les
journées simulées sont en fait **thermiquement typiques** de la fenêtre d'enquête
(56ᵉ à 81ᵉ centile), et **27,7 % des séquences de cinq jours consécutifs de la période
d'enquête sont elles aussi entièrement sèches**

Ce qui reste, et qui se sépare en deux remèdes distincts : les jeux de test gelés moyennent
correctement la météo mais sur l'année entière, d'où un biais **thermique de +5,3 °C** qui se
corrige en restreignant leur tirage à la fenêtre ; un run, lui, ne moyenne pas du tout, et
**aucun choix de dates n'y changera rien**. C'est une limite de variance : on l'annonce, on
allonge l'horizon, ou on tire la météo dans la distribution de la fenêtre plutôt que de
rejouer des jours consécutifs.

Source de la vérification : [méthodologie des Enquêtes Mobilité Certifiées
Cerema](https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie),
recoupée sur les dates de référence des microdonnées.

**Le parking-relais : 1,4 point en moyenne, mais six dixièmes de la cible sur les longs
trajets.** L'écart sur la définition du mode principal a été remesuré par territoire et par
distance (ticket 022). Le chiffre global était trompeusement rassurant.

**Before :** « 1,4 point de la cible transports collectifs est hors d'atteinte »
**After :** « 3 % de la cible à Toulouse, mais **31 % en 2ᵉ couronne** ; 3 % sur les trajets
de 2 à 5 km, mais **39 % de 10 à 20 km et 59 % de 20 à 50 km** »

Autrement dit : sur les longs trajets, près de six dixièmes de l'objectif « transports
collectifs » correspondent à des gens qui prennent leur voiture jusqu'à un parking-relais
puis le métro — un trajet que la simulation ne sait pas proposer. Le modèle est jugé, sur
cette tranche, contre un objectif qu'il ne peut pas approcher, et il en est « corrigé »
d'autant.

**Le piège à éviter, dit avant que quelqu'un s'y jette :** retirer ces trajets de l'objectif
serait faux. Ces voyageurs se déplacent quand même — privés du trajet mixte, ils feront tout
en voiture ou tout en transports collectifs, et on ne sait pas lequel. L'objectif atteignable
est donc un **intervalle**, pas un chiffre : entre 4,8 et 7 % pour la 2ᵉ couronne, entre 5,3
et 13 % sur les trajets de 20 à 50 km.

**Deux tickets ouverts sur cet audit, et leurs corrections vont dans des sens opposés** —
c'est ce qui les rend faciles à confondre :

| | Ticket 021 (territoires) | Ticket 022 (parking-relais) |
|---|---|---|
| Effet attendu sur la note | elle **se dégrade** (47,8 → 50,7) | elle **s'améliore** |
| Pourquoi c'est acceptable | retire un avantage non mérité | élargit un objectif inatteignable |
| Ce qu'il faut donc exiger | rien de plus | une justification **territoire par territoire** |

Une neutralisation qui améliore la note sans être justifiée strate par strate est
indistinguable d'un objectif ajusté pour arranger — ce que le protocole du projet interdit.

**Un troisième ticket, et un verrou qui manquait à tout le monde.** La moitié corrigeable de
l'écart de météo — les jeux de test tirent leurs journées dans l'année entière au lieu des
cinq mois de l'enquête — part en correction (ticket 023) selon le protocole du projet pour ce
genre de paramètre. Elle est déjà chiffrée **sans avoir dépensé un seul appel au modèle** :
**−4,9 °C** sur la température vue par le prompt, et **aucun effet annonçable sur la pluie**.

Ce dernier point vient d'un contrôle qui a renversé une lecture. En comparant le changement de
fenêtre à un simple **re-tirage sans changement de fenêtre**, on constate que la fenêtre
déplace l'exposition à la pluie de 1,2 point là où le re-tirage seul la déplace de 5,1. L'effet
« pluie » était du bruit. Il est maintenant interdit de le conclure, quel que soit le résultat
de la mesure — c'est écrit comme critère.

**Before :** le protocole prescrivait un témoin qui n'existe que si la correction touche une
petite partie du jeu de test
**After :** il prescrit aussi le cas inverse — ici la correction touche 98,9 % du jeu, le
témoin habituel ne pèse plus que 23 enregistrements, et il faut un **témoin nul à pleine
masse** à la place

**Et une procédure ne s'exécute plus pendant qu'une simulation tourne.** Un jeton
d'exclusion (`make protocol-lock`) refuse de se prendre si un run est actif, et enregistre
l'état des quotas à la prise et au relâchement. La raison n'est pas l'hygiène : mesure et
simulation puisent dans le même quota, et si un fournisseur sature entre les deux moitiés
d'une comparaison, les deux moitiés n'ont pas été évaluées par le même modèle. L'écart
mesuré ne veut plus rien dire, et rien dans les résultats ne le signale. Le jeton devient
l'étape 0 du protocole.

Limite écrite noir sur blanc plutôt que contournée : ce verrou est **local** et n'atteint
pas la campagne de calibration qui tourne en autonomie sur une machine distante. La mettre
en pause reste une case à cocher, pas une garantie du verrou.

---

## [2026-08-24] Le gain du temps terminal, remesuré sur son vrai périmètre

Le chiffre publié pour l'alignement du temps terminal (`tt3`) était **plus favorable que la
réalité**, parce que la mesure portait sur moins que la livraison. Il est corrigé partout.

L'A/B avait comparé `v5` (temps de la config) à `v6`, qui n'aligne que la **voiture** : gain
de 4,52 de composite. Mais `tt3`, en production, aligne aussi le **vélo** — 2,00 → 0,29 min
par option. Rendre le vélo plus rapide le rend plus attractif, donc *contre* le gain. Un
troisième jeu, `v7`, aligne les deux modes et mesure exactement ce qui tourne.

**Before :** « le temps terminal aligné gagne 5,28 de composite »
**After :** « il en gagne **2,17** ; aligner la voiture seule en aurait gagné 4,52, et
l'alignement du vélo rend 2,35 — la moitié »

| | v5 | v6 (voiture) | v7 (**livré**) |
|---|---|---|---|
| composite | 27,00 | 22,48 | **24,83** |
| vélo | 19,50 % | 15,16 % | 16,28 % (cible 4,0) |
| voiture | 38,88 % | 48,86 % | 47,69 % (cible 55,0) |

Rien ne change en production : la correction reste celle que la source réclame, et le vélo
à 1 min par bout n'était pas plus sourcé que la voiture à 3-7 min. Ce qui change est le
chiffre qu'on lui attribue, et l'argument de priorité qu'il portait — corriger une entrée
pèse *autant* qu'une calibration de prompt, non plus le double.

**Ce que l'incident a laissé dans l'outillage :**

- `rewrite_terminal_time.py` prend un `--modes` : le périmètre du jeu de test devient
  explicite, et huit tests vérifient qu'aligner la voiture laisse le vélo intact ;
- le rapport de dérivation donne le temps terminal **par mode** et non plus une moyenne
  commune. Celle-ci vaut 5,83 → 0,46 min pour `v7` : elle ne décrit ni la voiture (7,93 →
  0,55) ni le vélo (2,00 → 0,29), et c'est pourtant le chiffre qu'on aurait cité ;
- la page de mesure ne porte plus **aucun** chiffre écrit à la main — gain, dimensions,
  parts modales sont calculés depuis les traces. La version précédente en portait quinze,
  et ils décrivaient déjà un jeu périmé ;
- la page horodatée est écrite en **double** : dans `docs/synthesis/` où on la lit, et dans
  `docs/traces/` où elle survit — `docs/synthesis/*` est gitignoré.

**Un piège de cache à connaître.** Ajouter le mode à la clé de tirage a changé le *contenu*
de `v6` sans changer son *nom* ; la clé de cache d'éval (`ds=v6`) porte le nom, pas une
empreinte du contenu. L'éval en cache décrivait un jeu qui n'existait plus, et il a fallu la
purger à la main. Toute modification du mécanisme de tirage invalide les évals des jeux
qu'il a produits, et le store ne le détectera pas pour vous.

Traces : `docs/traces/2026-08-24_temps_terminal/` · page :
`docs/traces/2026-08-24_temps_terminal/2026-08-24_12-03_temps_terminal.html`

---

## [2026-08-24] Le portefeuille de tickets recentré sur la base de population

Arbitrage de priorité : **les données d'entrée passent devant la calibration**. Le gain
mesuré sur le seul calibre du temps terminal (2,17 de composite sur le périmètre livré)
est du même ordre que celui de la calibration de prompt (3,67), et il vient d'un défaut de
population, pas de formulation. Calibrer un prompt contre une base biaisée revient à
calibrer l'instrument sur le biais.

**Chiffre révisé le 2026-08-24.** L'arbitrage s'appuyait d'abord sur 5,28, mesurés en
n'alignant que la voiture alors que la production alignait aussi le vélo. Le bras `v7`,
qui aligne les deux, donne 2,17. L'arbitrage tient — un seul paramètre exogène pèse autant
que toute une calibration de texte — mais il ne tient plus « largement ».

**Deux chantiers mis en veille** — `004` (industrialisation de la calibration de prompt) et
`009` (calibration génétique, dont le résultat n'est pas significatif). Rien ne les bloque :
c'est une décision de séquence, le travail reprendra tel quel. La campagne génétique
**continue de tourner** en tâche de fond sur la VM, elle n'est simplement plus un chantier
instruit.

**Deux chantiers abandonnés** — `006` (relance du run de référence) et `010` (validation du
drainage nocturne). Tous deux devaient être jugés sur les runs des 19-21 août ; on repart
d'un **nouveau jeu de test**, et rejouer leurs critères mesurerait une base qu'on ne veut
plus. Le code du 010 (A1–A4) **reste en production** : c'est son volet de validation qui est
abandonné, pas sa livraison.

**Un ticket ouvert — `020`, « la même base ? »** Toute la chaîne de mesure compare des parts
modales simulées aux cibles CEREMA dans huit sous-catégories, et cette comparaison n'a de
sens que si les deux côtés parlent de la même population. Ce n'était jamais vérifié, c'était
supposé. Trois écarts sont déjà établis à la seule lecture du dépôt :

- les caractéristiques de la population enquêtée (453 communes, 1,32 M de 5 ans et plus,
  674 000 ménages, variables de redressement) sont documentées dans
  `population_emc2_2023.yaml` — qu'**aucun code ne lit**, et dont l'essentiel dort en
  commentaire ;
- les couronnes sont classées par **distance** à l'hypercentre (8/20/40 km) là où l'enquête
  découpe par **liste de communes** (1/68/109/275), alors que le commentaire du code annonce
  l'inverse. La cible voiture vaut 31 % à Toulouse contre 64 % en 1ʳᵉ couronne — un agent
  mal classé est comparé à une cible qui diffère de 30 points, et depuis `tt3` ce même
  classement **facture** son temps terminal ;
- l'enquête couvre le 20/09/2022 – 18/02/2023 hors vacances scolaires, quand les jeux gelés
  tirent la météo dans **l'année entière** — sur le mode le plus sensible à la météo.

Six autres axes restent à mesurer (âge minimum de 5 ans, pondérations `COE0`/`COEP`,
populations exclues, jour de semaine, définition du déplacement à mode principal,
représentativité spatiale). Chaque axe recevra un verdict écrit : corriger, neutraliser dans
le scoring, ou publier comme limite. Un axe non mesuré est un axe qui passe.

**Priorités confirmées** — `016` (abonnement TC) et `017` (permis) restent les chantiers de
tête ; `011` (arrivées perdues GAMA) est maintenu en priorité basse, son échéance réelle
étant le passage à 10 000 agents et non le prochain run.

**Troisième mise en veille : `012`** (mémoïsation des réflexions). Le code reste en
production — seule la mesure A3 est suspendue : elle demande de rejouer deux fois un
scénario épinglé, et ce scénario change avec le nouveau jeu de test. Elle garde tout son
intérêt là-bas : chaque réflexion vaut une requête pleine sur le quota jour, et c'est le
poste que les replays d'itération font payer deux fois.

**`013` et `014` restent ouverts.** Pour le `014`, les **deux** options restent instruites :
l'analyse recommandait d'abandonner l'option 2 (le prompt-journée), au motif que son
bénéfice *tour-based* est atteint par l'option 3 sans sa rupture de granularité de mesure ;
cette recommandation n'est pas retenue.

**Deux rejets.** `002` (snapshot du plan 24 h) : sa réutilisation était conditionnée à un
hash de population, et chaque chantier en cours change la population — le snapshot serait
écrit puis jeté à chaque itération. Le filet suffit : les caches OTP/OSMnx/LLM ne sont pas
invalidés par un changement de trait, un itinéraire restant valide même si l'agent gagne un
abonnement de bus. Et le **lot 4 du `015`**, qui remontait la loi du vélo dans le fork
eqasim : le post-traitement étant obligatoire dans tous les cas, la même loi n'a pas à vivre
à deux endroits — le doublon n'apporterait qu'un risque de dérive entre deux
implémentations. La crainte d'une population régénérée qui retrouverait l'ancien gradient en
silence ne tient pas : le contrôleur lève une `[ALARME]` en ERROR sur `personal_bike`
absent, compte les agents concernés et les traite sans vélo. L'échec est déjà détecté.

Le `015` n'attend donc plus qu'une chose : un run neuf pour rafraîchir les chiffres de son
volet 3, aujourd'hui lus sur un run archivé dont les personas portent encore l'ancien
gradient. Cette relance était le ticket `006`, abandonné — la dépendance bascule sur le
nouveau jeu de test.

**`018` : la méthode de test est arrêtée d'avance.** Au signal de l'utilisateur, le partage
de la voiture du foyer sera testé selon
[`protocole-parametre-exogene.md`](arch/protocole-parametre-exogene.md) — mesure d'enquête,
jeu gelé, A/B apparié, archivage, porte de décision — donc **chiffré sans payer de run**.
Deux limites du protocole mordent sur ce ticket et sont inscrites dans le ticket : la
réécriture d'un jeu gelé ne change pas *quelles* options ont été offertes (c'est justement
l'objet de son option A) et ne rejoue pas les chaînes de véhicule (or la rivalité
intra-foyer est un phénomène de chaîne). Le protocole peut donc trancher le **niveau** de
`car_availability` à coût quasi nul, pas l'effet d'une vraie rivalité.

**Nouveau statut de ticket : `en veille`.** Distinct de `bloqué`, qui dit qu'une dépendance
extérieure manque — les confondre ferait chercher un déblocage qui n'existe pas.

---

## [2026-08-24] Temps terminal : la correction passe en production (tt3)

L'alignement mesuré ce matin est désormais **le comportement par défaut**.
`llm-agents/config/terminal_time.yaml` passe en `version: tt3` : le temps d'accès et de
stationnement n'est plus une constante par couronne, il est **tiré dans la loi mesurée sur
EMC²**. `routing_version` reste à `r1` — le temps réseau ne change pas, donc les milliers
de routes OSMnx ne sont pas recalculées (~2 h évitées).

**Before :** `car: Temps de trajet : 10 minutes, dont 10 minutes d'accès et de
stationnement. Distance : 47 m.` — 8 secondes de conduite, 10 minutes de stationnement.
**After :** le même trajet tire son temps terminal dans la loi d'enquête, qui vaut 0 dans
88 à 96 % des cas selon la couronne.

**Le vélo aussi.** En `tt2` il portait 60 s par bout, marqués `provenance: unsourced` faute
de source publiée pour le temps terminal d'un vélo *personnel*. L'enquête en donne une :
0,11 min par bout (`T3 ∈ {11, 17}`, 2 047 trajets). Les deux modes véhiculés sont donc
sourcés, et corriger la voiture seule aurait laissé un biais non documenté en face d'un
biais corrigé.

**Trois pièges fermés au passage**, parce qu'un paramètre tiré n'est pas un paramètre
constant :

- **la grille de sensibilité effaçait les lois.** `apply_variant` reconstruisait le profil
  sans les champs de loi : les variantes `low`/`high` retombaient sur les constantes,
  nulles depuis `tt3`. La grille aurait mesuré « avec ou sans temps terminal » au lieu de
  « plus ou moins », sous une étiquette de variante juste. Elle met désormais la **loi** à
  l'échelle, en fusionnant les masses des clés qui collisionnent — la loi somme toujours
  à 1 ;
- **le tirage devait être déterministe.** Les plans et les décisions LLM sont mis en
  cache ; un tirage aléatoire ferait diverger un run de sa reprise et rendrait le cache de
  décisions faux. La clé est le trajet — mode et couple origine-destination à ~1 m près ;
- **le rendu impose des minutes entières.** Les clés de la loi sont en minutes, donc
  multiples de 60 s par construction : l'invariant « total affiché = somme des sous-étapes
  affichées » tient sans avoir à le vérifier.

**Une fuite d'isolation de tests, découverte par le garde-fou d'alignement.** Le helper
`_write_config` réassignait `terminal_time._CONFIG_PATH` vers un fichier temporaire sans le
remettre : tout test exécuté après un test de configuration lisait un YAML jeté dans
`tmp_path`. La fuite était invisible tant qu'aucun test ne dépendait des valeurs de
production — le nouveau garde-fou, lui, en dépend : il passait seul et tombait en suite.

**Ce qui est verrouillé maintenant.** 56 tests sur le temps terminal, dont un garde-fou qui
**refuse un retour aux valeurs `tt2`** : si l'espérance servie sortait de la fourchette de
l'enquête, il échoue. C'est exactement la régression qui a coûté 2 points de composite au
run du 21 août, et elle ne peut plus passer inaperçue.

Le bloc `modes:` du YAML est **généré**, pas recopié : `make terminal-time` réémet la loi
depuis l'enquête (`--emit-config`). Une centaine de nombres maintenus à la main
dériveraient.

**Traces archivées** dans `docs/traces/2026-08-24_temps_terminal/` — `index.html` pour la lecture au navigateur, `README.md` et `results.json` à côté. Et une page de mesure **horodatée avec ses graphiques** dans `docs/synthesis/2026-08-24_11-31_temps_terminal.html` (`make terminal-page`), au même endroit et dans le même langage visuel que la page de synthèse principale — le store de
calibration et les jeux `v6` étant gitignorés, les résultats agrégés y sont committés avec
de quoi les retracer (empreintes de nœuds, clés de paramètres, effectifs).

**Reste à faire, et c'est la partie qui coûte :** un run de simulation neuf. Les mesures
portent sur des jeux gelés — elles disent ce que le modèle choisirait, pas ce qu'une
simulation produirait, la réécriture ne rejouant ni l'offre d'options ni les chaînes de
véhicule. La grille de sensibilité (T6 du ticket 013) reste par ailleurs à parcourir.

---

## [2026-08-24] Le temps de stationnement aligné sur l'enquête : −5,3 sur le composite

Suite du diagnostic du même jour. `llm-agents/config/terminal_time.yaml` applique 2 à
10 minutes d'accès et de stationnement par trajet voiture, sourcées sur la littérature
(tables COMPASS, Shoup, Cerema). L'enquête que le projet prend pour cible **le mesure**, et
en trouve 8 à 24 fois moins.

`make terminal-time` extrait la loi depuis le fichier trajets d'EMC² — `T2` (marche au
départ), `T6` (marche à l'arrivée), `T11` (durée de recherche du stationnement) :

| couronne | accès : enquête / config | égression : enquête / config |
|---|---|---|
| Toulouse | 0,36 / **3** min | 0,52 / **7** min |
| 1ʳᵉ couronne | 0,14 / 2 | 0,17 / 4 |
| 2ᵉ couronne | 0,16 / 2 | 0,19 / 3 |
| 3ᵉ couronne | 0,09 / 1 | 0,06 / 1 |

**Le doute a été levé avant de conclure.** Si EMC² codait la marche vers la voiture comme un
trajet à pied distinct, `T2`/`T6` vaudraient 0 par construction et la comparaison serait
vide. Vérifié : sur les 24 481 déplacements comportant un trajet voiture, **aucun** ne porte
de trajet à pied. Et l'instrument fonctionne — sur les trajets en transports collectifs, de
structure identique, `T2 + T6` donne 6 minutes en médiane. L'enquête sait enregistrer un
temps terminal ; elle en enregistre 0,55 min pour la voiture.

**Mesuré, sans rejouer de simulation.** Les jeux gelés portent les composantes décomposées
sous-puce par sous-puce, et le temps terminal est additif et séparable du temps réseau — la
config acte déjà cette séparation en versionnant à part les plans et le routage. Les jeux
dérivés sont donc `v5` avec les seules jambes terminales réécrites, temps de conduite
intact, offre d'options intacte.

**Trois bras, parce que deux mesuraient moins que ce qui part en production.** `v6` aligne
la **voiture** seule ; `v7` aligne **voiture et vélo**, soit le périmètre exact de `tt3`.
Le vélo passe lui aussi de 2,00 à 0,29 min par option, ce qui le rend plus attractif — dans
le sens *inverse* du gain. La mesure honnête est celle de `v7`.

Résultat de l'A/B apparié (même prompt de production, 223 décisions, 75 personas) :

| | v5 (config) | v6 (voiture) | v7 (**livré**) | écart livré | cible EMC² |
|---|---|---|---|---|---|
| **composite** | 27,00 | 22,48 | **24,83** | **−2,17** | |
| global | 7,80 | 4,84 | 5,78 | −2,01 | |
| genre | 8,16 | 5,37 | 6,18 | −1,98 | |
| motif | 8,21 | 9,13 | 9,50 | **+1,29** | |
| distance | 8,37 | 11,62 | 10,95 | **+2,59** | |
| **vélo** | 19,50 % | 15,16 % | **16,28 %** | −3,22 | 4,0 % |
| **voiture** | 38,88 % | 48,86 % | **47,69 %** | +8,81 | 55,0 % |
| marche | 16,07 % | 14,57 % | 13,48 % | −2,59 | 26,0 % |
| TC | 25,55 % | 21,41 % | 22,56 % | −3,00 | 12,0 % |

**Before :** `car: Temps de trajet : 10 minutes, dont 10 minutes d'accès et de
stationnement. Distance : 47 m.` — 8 secondes de conduite.
**After :** `car: Temps de trajet : 0 minute. Distance : 47 m.`

Le gain de **2,17** est à comparer aux **3,67** que la calibration de prompt a gagnés sur le
même jeu commun. Aligner la voiture seule aurait rapporté 4,52 ; aligner le vélo en rend
2,35, soit la moitié. Corriger l'entrée reste du même ordre qu'optimiser le texte, et non
plus nettement au-dessus : c'est une révision à la baisse de l'argument, et elle est due.

**Ce n'est pas gratuit, et il faut le dire.** Les dimensions `distance` (+2,59) et `motif`
(+1,29) se **dégradent** : le vélo reste 4× au-dessus de la cible et la marche s'en éloigne
(13,5 % contre 26,0 attendus). L'alignement corrige un biais dominant, il ne résout pas la
sous-représentation de la marche.

**Portée de la mesure.** Elle dit ce que le modèle choisirait avec des temps corrigés, pas
ce que la simulation produirait : la réécriture ne rejoue ni l'offre d'options ni les
chaînes de véhicule, où le choix d'un jour se répercute sur les offres du lendemain. La
correction en production (`terminal_time.yaml` + bump de `version`, sans toucher
`routing_version`) et un run neuf restent à faire.

Ce n'est pas l'ajustement que la décision T2 du ticket 013 interdit : T2 interdit de régler
ce paramètre **sur un score**. Il est ici re-sourcé sur la mesure d'enquête, ce que son
propre `provenance: sourced` réclame — et aucune valeur n'a été choisie en regardant une
part modale.

---

## [2026-08-24] La régression du run du 21 août vient du temps de stationnement, pas du prompt

Le run du 21 août score **22,17** contre **20,11** au run du 2 août sur la loss du moteur de
calibration — soit +2,06, moins bon — avec un vélo à 20,4 % pour une cible de 4,1 % et une
voiture tombée à 46,5 % pour 56,7 % attendus. Quatre causes étaient plausibles ; trois sont
écartées par la mesure, et la quatrième n'était pas sur la liste.

**Ce n'est pas la population.** L'offre de vélo est identique d'un run à l'autre (33,1 % →
33,6 % des décisions) et l'équipement du run est conforme à l'enquête : 49,6 % de porteurs
pour ~49,4 % attendus, gradient de taille de ménage croissant. Le nouveau trait
`personal_bike` ne déplace pas les parts modales.

**Ce n'est pas le prompt.** Le prompt de production `expert_chaine` ne diffère de `expert`
que par une puce — « Chaîne de la journée : en cas d'utilisation d'un véhicule personnel
(vélo, trottinette, voiture…), pense au stationnement… ». Un A/B **apparié** des deux
textes, sur le jeu gelé `rank` et sous le régime de la campagne `ref2`, donne 19,39 % de
vélo contre 19,50 % : **+0,11 point**. La puce est hors de cause, et le composite ne bouge
que de sa pénalité de longueur.

**Ce n'est pas la composition des décisions.** Décomposition par bande de distance :
+1,0 point vient du changement de quelles décisions se voient offrir un vélo, +12,4 points
du taux de prise **à distance constante**.

**C'est le temps terminal des itinéraires (ticket 013).** Sur les trajets de 0,5 à 6 km, le
temps affiché au LLM est passé de 3,9 à **5,4 min/km pour la voiture** (+38 %), tandis que le
vélo reste à 4,4 et la marche à 12,4. Le temps d'accès et de stationnement a bien été ajouté
aux deux modes, mais il pèse trois fois plus sur la voiture — 6 minutes pour rejoindre et
garer une voiture contre 2 pour déverrouiller et attacher un vélo.

**Before :** `car: Durée estimée : 27 minutes. Distance : 11.3 km.`
**After :** `car: Temps de trajet : 8 minutes, dont 6 minutes d'accès et de stationnement.
Distance : 760 m.`

À 2,3 km, la voiture passe de 9 à 13 minutes quand le vélo reste à 10 : **le vélo double la
voiture**. Le taux de prise du vélo monte dans toutes les bandes de distance sauf sous 1 km,
avec un maximum de +20 à +40 points entre 1 et 3 km — exactement là où quatre minutes
renversent le classement.

Le principe du ticket 013 n'est pas en cause : se garer coûte du temps, et l'ignorer était
un biais en faveur de la voiture. C'est son **calibre** qui est à confronter à l'enquête —
6 minutes d'accès et de stationnement sur *tout* trajet en voiture, y compris de 760 mètres.
Et le prompt en service n'a jamais été recalibré sous ce nouveau régime de temps.

Outillage ajouté : `prompt_calibration/ab_chaine.py` compare deux prompts sur un jeu gelé
avec les mécanismes de la calibration (même `Evaluator`, même loss, même store
content-addressed) sans lancer de campagne — 30 appels LLM au lieu des centaines qu'aurait
coûté l'attribution initiale d'un `calibrate run`. Il chiffre avant de dépenser
(`--dry-run`) et refuse le jeu `test`, réservé au regard unique du protocole.

---

## [2026-08-21] Les familles dans les maisons, les personnes seules dans les appartements

Le type de logement d'un persona ne dépendait que d'une chose : **où** il habite. Dans une
même zone fine, un célibataire et une famille de quatre tiraient dans la même loi — alors
que l'enquête voit 15,7 % de personnes seules en maison individuelle isolée contre 53,9 %
des ménages de quatre et plus. Le gradient était aplati, et dans la population synthétique
carrément **inversé** : 29,0 % pour une personne seule, 38,5 % à quatre.

La loi du logement est désormais conditionnée à la **taille du ménage** autant qu'à la zone.
La géographie fixe le niveau, la taille déplace les modalités les unes par rapport aux
autres, puis on renormalise. La taille utilisée est celle que le persona **déclare**, jamais
le nombre de ses colocataires présents dans le fichier — un quart des foyers y sont
incomplets, et les compter mettrait des familles dans des lois de personne seule.

**Avant :** 29,0 / 41,8 / 38,5 / 38,5 % d'individuel isolé pour les tailles 1 à 4 — pente
+9,5 point, quand l'enquête en voit +38.
**Après :** 14,5 / 41,8 / 36,9 / 52,1 % — pente **+37,6 point**. Mesurée à l'intérieur de
l'enquête, sur des ménages dont on connaît la vérité, l'erreur du mécanisme tombe de
**3,00 à 0,75 point** sur les vingt cellules (cinq types de logement × quatre tailles), et
la marginale d'ensemble ne bouge pas : le levier déplace les tailles, pas la géographie.

**Ce que ça débloque, et c'était la raison d'être du chantier.** L'axe habitat sert à valider
l'équipement vélo (ticket 015), mais il ne pouvait pas : le logement du persona étant lui-même
imputé, il ne coïncidait avec le vrai qu'une fois sur deux, ce qui plafonnait l'amplitude
mesurable à 19,9 points au lieu des 33,4 publiés. L'accord monte à **50,2 %** et l'amplitude
opposable à **26,8 points** — **+6,9 points regagnés sans qu'une ligne du modèle vélo bouge**.
Le contrôle a été rejoué et il passe, à +0,1 à +2,3 points de la cible sur les quatre types
d'habitat.

Le premier rejeu, lui, montrait un biais de 1 à 9 points **sous** la cible, du même signe
partout — donc pas du bruit. Il ne venait pas du modèle vélo mais d'une **confusion
d'unité** : la cible comptait des *ménages équipés* (un foyer compte pour un dès qu'il a un
vélo) quand la population mesure des *personnes dotées* (dans un foyer de quatre avec un
vélo, une seule personne le porte). L'écart entre les deux suit la taille du ménage, et
c'est pourquoi il était maximal en maison individuelle. Les deux grandeurs sont désormais
servies séparément, et un test échoue si on recalcule l'une avec la formule de l'autre.

**Trois refus explicites**, parce qu'un trait imputé qui se replie en silence est pire qu'un
trait absent :

- une population dont le trait manque **en masse** fait désormais **échouer** la validation
  au lieu de la réussir par vacuité ; une population trop petite pour trancher a son propre
  code de sortie, qui ne dit ni succès ni échec ;
- un persona **sans taille de ménage** ne reçoit aucun logement — retomber sur la loi de zone
  ferait rentrer le défaut par la fenêtre ;
- la ressource est **versionnée** : celle d'avant est refusée au chargement, avec la commande
  à lancer. Un déploiement à moitié fait s'arrête au lieu d'imputer à l'ancienne.

Le sel de tirage passe à `housing_type_v2` : **toutes** les imputations existantes sont
rebattues, y compris celles qui n'auraient pas changé de loi. C'est délibéré et daté ; les
populations 10 / 100 / 1 000 sont ré-imputées.

---

## [2026-08-21] Le notebook de génération va enfin jusqu'au bout

Le notebook de population s'arrêtait dans son dossier de travail. Les cinq étapes
tournaient, produisaient un résultat correct dans `Temp/5_scheduled/`… et personne ne le
recopiait vers `data/population/`, seul dossier que lisent GAMA et le serveur d'agents. Le
fichier qui s'y trouvait était donc la sortie **brute** d'eqasim, déposée par l'étape 1 et
jamais remplacée.

Ce n'est pas un détail de plomberie. `toulouse_population_1000.json` portait **0 activité
planifiée** là où `Temp/5_scheduled/` en comptait **3 944** : la population servie à la
simulation n'avait ni activités corrigées, ni flag de desserte TC, ni horaires recalés sur
les temps de trajet réels. Et rien ne le signalait, parce que le fichier était par ailleurs
parfaitement valide.

Trois étapes ont été ajoutées :

- **7 — export final** vers `data/population/`, qui **refuse** d'écraser une population
  valide par une population dégradée (aucune activité planifiée, ordre temporel invalide,
  ou perte de la moitié des agents) et laisse un `.bak` ;
- **8 — traits imputés depuis EMC²** : `fix_minor_traits`, puis `enrich_housing_type`, puis
  `enrich_personal_bike` — dans cet ordre, le dernier lisant le trait du deuxième. Ces
  imputations n'étaient posées que si quelqu'un pensait à lancer les scripts à la main ;
- **9 — audit de complétude**, qui rend un verdict **POPULATION COMPLÈTE / INCOMPLÈTE** sur
  la présence des neuf traits que la simulation consomme.

**Un trait manquant n'est plus silencieux.** C'est le fond du problème : les consommateurs
en aval ne se plaignent pas tous d'une donnée absente. `personal_bike` manquant était traité
comme « vélo normal » jusqu'à hier — 100 % des agents à vélo, sans une ligne de log. L'audit
prononce donc un verdict sévère plutôt qu'un avertissement, et l'étape 8 distingue trois
sorties : trait posé, trait **impossible** à poser (ressource d'accès restreint absente —
elle dit laquelle produire), et population **enrichie mais trop petite pour être validée**
— ce dernier cas n'étant pas un échec, une population de 10 agents ne pouvant arbitrer
aucun croisement.

**Before :** notebook exécuté → `data/population/` contenait la sortie brute d'eqasim, sans
horaires recalés ni traits imputés ; il fallait connaître trois commandes et leur ordre.
**After :** notebook exécuté → population complète, vérifiée, avec un verdict explicite.

---

## [2026-08-21] Le vélo de l'agent, appris sur l'enquête au lieu d'être hérité d'un inconnu

Le vélo d'un persona venait d'un ménage réel de l'ENTD 2008 tiré au sort — mais apparié
**sans** la taille du foyer ni le type d'habitat. Un célibataire toulousain héritait donc
des trois vélos d'une famille de cinq, et une famille de cinq du zéro vélo d'un couple âgé.
Le total tombait à peu près juste, ce qui masquait tout : le gradient de taille de ménage
était **inversé**.

`personal_bike` est désormais produit en trois étages appris sur EMC² Toulouse 2023 : le
**nombre de vélos du foyer** est tiré d'abord (conditionné à la zone fine du domicile, à la
taille du ménage et à la motorisation), puis **attribué nominativement** par tirage sans
remise pondéré par la propension à pratiquer le vélo, puis **typé** en VAE à 7,7 % du parc.
Le tirage est déterministe par hachage de l'adresse : deux générations donnent le même parc.

**Avant :** 76 % des personnes seules avaient un vélo, contre 36 % dans les ménages de
quatre — l'inverse de l'enquête.
**Après :** 35 % / 50 % / 61 % / 68 % pour les tailles 1 à 4, contre 33 / 48 / 54 / 63 %
attendus. La pente est dans le bon sens, et le total ne bouge pas (50,3 % de porteurs pour
50,9 % observés).

Pourquoi tirer le stock du foyer d'abord, et pas redresser à la fin : l'équipement vélo est
un trait de **ménage**, pas une pièce lancée pour chaque membre. Sur les familles de quatre,
l'enquête voit 16 % de foyers sans aucun vélo et 40 % avec un vélo par tête ; un tirage
individuel indépendant **calé sur la même moyenne** produit 1 % et 18 %, en empilant tout au
milieu. Les deux lois ont exactement la même moyenne — donc aucun redressement sur la
moyenne ne peut les rapprocher.

**Les vélos dormants sont conservés, exprès.** Onze points de la population tiennent un vélo
sans le pratiquer. Un vélo au garage est un vélo : c'est au choix modal et à l'agent de
décider de ne pas le prendre, pas à l'imputation de le faire disparaître.

**Une population sans le trait ne roule plus en silence.** `personal_bike` absent valait
« vélo normal » par rétrocompatibilité, ce qui mettait 100 % des agents à vélo sans une
ligne de log — sur le mode le plus scruté du projet. Le défaut est désormais « pas de vélo »,
et l'alarme sonne (`make error`).

**La politique de choix modal a été ré-entraînée sur la même définition.** Elle apprenait
« il y a un vélo dans le foyer » (63 % des personnes) et l'appliquait à une attribution
nominative (50 %) : le coefficient portait sur autre chose que ce qu'il mesurait. Les deux
côtés reconstruisent maintenant la même variable (spec v2, `make policy`). L'ajustement ne
bouge pas — ce n'était pas le but, c'était la cohérence.

**Trois critères de recette ont été restatés, mesure à l'appui**, parce qu'ils étaient
inatteignables comme écrits — et c'est peut-être le résultat le plus utile de ce lot :

- « 71 % en individuel isolé contre 38 % en grand collectif » est en outre une part de
  **ménages** équipés, quand `personal_bike` est un trait **individuel** : la cible servie
  est donc exprimée en part de **personnes** dotées. Confondre les deux unités biaise les
  quatre modalités dans le même sens, d'autant plus fort que l'habitat est familial (−10 pts
  en individuel isolé, −3 en grand collectif) — un foyer de quatre à un vélo est « équipé »
  mais un seul de ses membres est doté. Corrigé, les écarts tombent de −0,9…−8,6 à
  **+0,1…+2,3 points**. Et le critère lui-même ne peut pas être vérifié sur
  une population synthétique : le type de logement d'un persona est lui-même imputé et n'est
  juste qu'une fois sur deux, ce qui écrase l'amplitude mesurable, même avec le vrai nombre
  de vélos de l'enquête. La cible opposable est la courbe **diluée**, recalculée à chaque
  export — et elle s'est déjà resserrée toute seule de 19,9 à **26,8 points** à la livraison
  du ticket 019, sans qu'une ligne du modèle vélo change et sans que la population cesse de
  la tenir. C'est la meilleure preuve qu'on mesurait la dilution, et non un défaut du vélo.
- « 1,22 vélo par ménage » compte des vélos que le mécanisme ne représente pas exprès (le
  cinquième vélo d'un foyer de deux, qui n'a personne pour le porter).
- les cibles par catégorie sont désormais **standardisées** sur la composition réellement
  mesurée, et leur précision se calcule en **ménages** et non en personnes — le nombre de
  vélos est tiré une fois par foyer, deux frères ne sont pas deux observations.

Et une cellule sans matière n'est plus « réussie » : sous 30 ménages elle est **non
concluante**, et si aucun contrôle ne tranche, la validation **échoue**. La population de
10 agents ne peut donc plus décrocher un sans-faute en ne mesurant rien.

Le correctif est aussi remonté dans le fork eqasim, pour qu'une génération neuve soit juste
sans post-traitement. Il n'a **pas été rejoué** : la chaîne est exécutable (les données
sources sont là) mais demande un `docker compose build eqasim` — le stage importe désormais
`llm_module` — puis une régénération complète.

Détail, décisions et cibles : `docs/arch/velo-equipement.md`.

---

## [2026-08-21] L'habitat imputé sans la taille du ménage

Le type de logement d'un persona est tiré dans la loi de sa zone fine — et **seulement** dans
celle-là. Dans une même zone, les familles sont dans les maisons et les personnes seules dans
les appartements ; le tirage par zone mélange les deux.

Le mécanisme a été mis à l'épreuve **à l'intérieur d'EMC²**, en le faisant tourner sur des
ménages dont on connaît la vérité : la part d'individuel isolé qu'il attribue aux personnes
seules vaut 25,4 % quand la réalité est de 15,7 %, et 49,4 % aux ménages de quatre et plus
contre 53,9 %. Dans la population synthétique, la pente est carrément inversée — 27,2 % pour
une personne seule, 36,1 % à quatre et plus.

**Ça bloque la recette du vélo.** Le deuxième critère du ticket 015 valide l'équipement vélo
par type d'habitat, 71 % en individuel isolé contre 38 % en grand collectif. Or **38 % de ce
gradient est de la composition de ménages** et non de l'habitat : standardisé sur la taille,
il tombe de 33,4 à 20,8 points. Valider les vélos sur cet axe suppose donc que le croisement
habitat × taille soit juste — il ne l'est pas.

`docs/tickets/ticket_019_habitat_taille_menage.md` spécifie la reprise, et la règle proposée
est **testée avant d'être écrite** : loi de zone multipliée par un levier de taille estimé au
périmètre, puis renormalisée. L'erreur absolue moyenne passe de 2,62 à 0,63 point sur les
vingt cellules, et la géographie ne bouge pas (34,7 % d'individuel isolé en marginale
d'ensemble, 34,9 % après correction). La loi brute par (zone, taille) était hors de portée :
trois ménages par cellule en médiane. Le ticket n'a pas de volet eqasim — `housing_type` est
posé après coup, une ré-imputation suffit.

Deux autres candidats du même balayage sont **clos par décision**, et la trace est écrite là
où elle sera relue : le libellé de revenu, qui mesure une taille de ménage autant qu'un
niveau de vie parce que l'unité de consommation est jetée après avoir servi
(`docs/arch/population-post-traitements.md`), et le deux-roues motorisé, mode réel à 0,85 %
des déplacements mesuré à zéro parce qu'absent (annexe du ticket 018). Aucun des deux n'est
corrigé ; les deux sont documentés.

**Avant :** l'axe habitat servait de critère de recette sans avoir jamais été testé.
**Après :** il est testé, chiffré, et sa correction est validée sur données réelles avant
d'être implémentée.

---

## [2026-08-21] Le vélo n'était pas seul : l'abonnement TC, le permis, la voiture

Le diagnostic du vélo a été rejoué sur tous les traits d'équipement de la population
synthétique, face aux mêmes microdonnées EMC² Toulouse 2023. **Quatre champs seulement sont
recopiés d'un donneur ENTD 2008** — permis, abonnement TC, statut de passager, nombre de
vélos — et deux d'entre eux souffrent exactement du mal du vélo : un total à peu près juste,
une répartition retournée.

**L'abonnement TC est le cas le plus grave, et le plus influent.** 21,9 % d'abonnés simulés
contre 25,8 % mesurés : quatre points d'écart en agrégat, mais les étudiants passent de
74,3 % à 36,7 % et les retraités de 17,7 % à 28,5 %. L'abonnement a changé de génération. Or
c'est le levier d'équipement le plus fort de la politique de choix modal — +9,7 points de TC
et −8,2 points de voiture, presque le double du vélo — donc la part TC globale reste presque
juste **pour les mauvaises personnes**.

**Le permis suit la même pente, en plus discret** : 91,5 % de titulaires simulés contre
85,9 % chez les majeurs, l'écart se concentrant sur les 18-24 ans (85,4 % contre 58,1 %). La
cause est commune aux deux : la classe d'âge de l'appariement couvre 15 à 29 ans d'un bloc,
alors que le permis y va de 0 % à 78 % et l'abonnement de 64 % à 29 %. Un donneur national de
2008 ne peut pas rendre une cohorte toulousaine de 2023.

**La voiture, elle, pose une autre question** : elle est traitée comme un bien personnel
alors qu'elle est partagée. 20,6 % des ménages motorisés comptent plus de titulaires que de
voitures, et 6,1 % des trajets voiture conduits d'un run de référence partent alors que
toutes les voitures du foyer sont déjà sorties.

Trois spécifications sont écrites : `docs/tickets/ticket_016_abonnement_tc_progedo.md`,
`ticket_017_permis_progedo.md` et `ticket_018_partage_voiture_foyer.md` (non prioritaire,
avec en annexe le deux-roues motorisé — 9 % des ménages, mesuré à zéro parce qu'absent).
Les 016 et 017 partagent leurs deux premiers lots : même fichier source, même cause, un seul
chargeur pour deux cibles. Et contrairement au vélo, ils **alignent** les définitions au lieu
de les écarter — la politique est déjà entraînée sur `P12` et `P7`, aucun ré-entraînement.

**Avant :** un seul trait d'équipement était confronté à l'enquête ; les trois autres
n'avaient jamais été mesurés.
**Après :** les quatre le sont, avec vingt-cinq critères de recette chiffrés et un ordre
de livraison qui tient compte des dépendances — le permis avant la voiture, dont il
désamorce l'essentiel du biais.

---

## [2026-08-21] Le vélo des agents : le total est bon, la répartition non

L'équipement vélo de la population synthétique a été confronté aux microdonnées EMC²
Toulouse 2023 (ProGEDO `lil-1750`) et au rapport d'enquête publié. Le volume tient :
53,3 % des agents ont un vélo, contre ~51 % attendus. **La répartition, elle, est
inversée** : l'équipement décroît avec la taille du ménage (76 % pour une personne seule,
25 % à cinq) quand l'enquête le voit croître (33 % → 84 %), et il est plat selon le type
d'habitat quand l'enquête va de 38 % à 71 %.

La cause est isolée : eqasim ne calcule pas le nombre de vélos d'un ménage, il le
**recopie** du ménage ENTD 2008 apparié — or l'appariement ne tient compte ni de la taille
du foyer ni de l'habitat. Un célibataire peut donc hériter des trois vélos d'une famille de
cinq. La formule de répartition interne, elle, est presque juste : à nombre de vélos donné,
elle ne s'écarte de l'enquête que de quelques points (sauf pour la personne seule).

`docs/tickets/ticket_015_acces_velo_progedo.md` spécifie la reprise : apprendre le nombre
de vélos du ménage sur EMC² (et non plus le recopier), puis l'attribuer nominativement
d'après la pratique déclarée — vélos dormants compris, car un vélo qu'on n'utilise pas
existe quand même. Un seul champ individuel en sortie, le ménage ne vit que le temps de la
génération.

**Avant :** l'équipement vélo était une formule non validée, sa seule trace vérifiable un
commentaire de code.
**Après :** un diagnostic reproductible sur données officielles, neuf cibles chiffrées de
validation, et quatre lots dont le premier ne demande aucun modèle.

Danger fermé au passage : `personal_bike` manquait dans 7 des 10 fichiers de
`data/population/` — dont celui de 10 000 agents — et `_owns_bike` traite le champ absent
comme « possède un vélo ». Un run parti d'un répertoire d'expérience neuf aurait équipé
100 % des agents en silence. Ces fichiers sont déplacés dans `data/population/old/`, hors
du champ du loader, avec la note qui explique pourquoi.

---

## [2026-08-21] D'où vient chaque attribut d'un agent

Un persona arrive au LLM avec 19 traits, et rien ne disait lesquels sortent du tirage
statistique d'eqasim, lesquels sont recodés à l'export, et lesquels sont **imputés** faute
de donnée. La question se posait à chaque lecture d'un prompt : « ce type de logement, il
est observé ou tiré ? ».

`docs/arch/population-post-traitements.md` répond attribut par attribut, en quatre étages
— fork eqasim, export JSON, notebook, correctifs de surface — avec la règle exacte
appliquée et son ancre dans le code.

Deux constats qui en sortent, notés dans la page :

- `bike_availability` (le vélo au niveau du ménage) est calculé, exporté en CSV, et
  **jamais lu** : son seul consommateur est l'export MATSim, hors de notre `run:`. Toute
  l'information vélo qui atteint l'agent passe par `personal_bike`, donc par une imputation
  individuelle.
- `number_of_vehicles`, à l'inverse, n'atteint pas l'agent mais pilote l'appariement HTS
  via `any_cars` — et comme il somme voitures et deux-roues, un ménage sans voiture mais
  motorisé est apparié comme « motorisé ».

**Avant :** l'origine d'un trait se reconstituait en lisant quatre fichiers dans trois
dépôts.
**Après :** une page, une ligne par transformation, l'ancre de code à côté.

---

## [2026-08-20] Le statut des tickets vit dans la conf, plus dans les tickets

Le tableau de bord annonçait « à faire, 0/15 » pour le ticket 008 dont les sept actions
sont livrées, et « sans statut » pour 9 tickets sur 15 — dont le 013, livré et documenté.
La déduction automatique en était la cause, et c'est structurel : quand les cases d'un
ticket sont ses **critères d'acceptation**, elles restent vides jusqu'au run de validation,
ce qui ne dit rien de l'avancement du travail.

Les quinze tickets ont désormais un statut explicite dans
`scripts/dashboard/tickets_status.yaml`, avec la note de ce sur quoi il s'appuie et de ce
qui reste. La déduction devient un repli, et une ligne « Source : cases » se lit comme une
entrée manquante dans la conf.

Les en-têtes de tickets ne portent plus de `**Statut**` : un statut recopié dans quinze
fichiers se périme en silence — c'est précisément ce qui était arrivé au ticket 014, qui
affirmait « réflexion ouverte, aucune décision » alors que son option 1 tournait en
production sous drapeau, mesurée, testée, avec le biais vélo déjà corrigé. Les tickets
gardent le récit de ce qui est **dans le code**, vérifiable fichier par fichier ; la conf
porte l'état.

**Avant :** 0 ticket « terminé », 9 « sans statut », un ticket livré affiché comme à faire.
**Après :** 6 terminés, 7 en cours, 2 à faire, 0 sans statut — et chacun dit pourquoi.

Piège fermé au passage : deux tickets distincts partagent le numéro 005 (choix modal
probabiliste / politique PROGEDO) et deux autres le 014 (anticipation / annexe). La clé de
surcharge doit être le **nom de fichier complet** — une clé courte appliquerait un seul
statut aux deux.

---

## [2026-08-20] Le détail par sous-catégorie, lisible sans dérouler toute la synthèse

Le sous-chapitre « Détail par sous-catégorie » des volets 1 (simulation LLM + tirage) et 3
(arbre de régression PROGEDO) existe désormais aussi en page autonome : les sept
dimensions à la suite — âge, distance, genre, occupation, motif, lieu de résidence, type de
logement — en pleine largeur, sans colonne de navigation à gauche. On peut ouvrir, envoyer
ou imprimer les profils modaux d'un seul volet sans embarquer les trois autres chapitres de
la synthèse.

La page de synthèse **garde** ses deux sous-chapitres : les nouvelles pages en sont un
extrait, pas un déplacement. Chaque sous-chapitre y renvoie vers sa page dédiée, et le
sommaire gagne un groupe « Pages dédiées ». Les cellules sont produites par le même code
de rendu que la page complète : un chiffre affiché sur une page dédiée est, par
construction, celui du volet dont elle est extraite.

**Avant :** un seul document de 216 ko ; montrer le détail âge × mode de la simulation
supposait de faire défiler la calibration et le modèle statistique.
**Après :** `docs/synthesis/detail_simulation.html` et `docs/synthesis/detail_progedo.html`
(65 ko chacune), régénérées par `make synthesis` à côté de `index.html` inchangée.

---

## [2026-08-20] Relecture : la grille de sensibilité ne se mesurait pas deux fois de suite

Sept défauts trouvés en relisant le travail non poussé, dont trois qui faussaient une
mesure ou un fichier de configuration.

**La grille de sensibilité du temps terminal donnait des valeurs inventées.** Enchaîner
deux variantes dans le même processus — ce que fait une boucle sur `low`, `central`,
`high` — multipliait leurs facteurs : après `high` puis `low`, la voiture payait 0,75 fois
son temps terminal au lieu de 0,5. L'étiquette de variante, elle, était juste, si bien que
la mesure T6 aurait rapporté un écart sous un nom de variante qui ne le décrivait pas.
La mise à l'échelle repart désormais des valeurs centrales, et un test enchaîne les
bascules dans les deux sens.

**`make providers` abîmait `providers.yaml`.** En commentant un modèle disparu de l'API, il
re-commentait au passage les blocs déjà commentés qui le suivaient (`# # groq_llama4:`) —
or un bloc commenté est une décision humaine, pas un brouillon. Les 28 lignes touchées le
2026-08-18 sont ramenées à un seul niveau de commentaire. Le fichier garde aussi ses droits
d'origine, au lieu de passer en 600 à chaque rafraîchissement.

**Deux avertissements à chaque `make`.** La cible `stop-run` était déclarée deux fois ; la
première recette, morte, est supprimée.

**Autres corrections.** Un plan voiture ne déclare plus « 10 min de marche » et 200 m de
distance de marche venus d'un repli interne — chercher une place n'est pas marcher. Une
réflexion STM déclenchée pile à l'heure de réveil de son agent n'a plus une échéance déjà
dépassée. La page de synthèse relève la version du jeu de train dans le store au lieu de la
supposer `v1` : quand la campagne rangera ses évals sous `train@v2`, la colonne train
n'aura pas disparu sans un mot, et les évals ainsi écartées sont désormais annoncées. La
page par modèle dédoublonne les tentatives comme la page principale, garde-fou compris.

**Ce que le correctif de population sait maintenant dire.** `fix_minor_traits` reconstitue
les ménages par coordonnées du domicile, mais la population exportée est un échantillon :
121 des 547 ménages y comptent moins de membres que ne l'annonce leur `household_size`. Les
permis des absents ne sont donc pas comptés et `car_availability` penche vers « voiture
toujours disponible ». 16 ménages ont même une voiture et aucun conducteur présent, alors
que leurs non-conducteurs restent éligibles au mode passager. Le script mesure et affiche
ces deux comptes au lieu de les laisser passer ; la correction de fond demande un
`household_id` à la génération.

**Notebooks.** `pipeline.ipynb` était committé dans l'état d'un `papermill` en échec —
bannière rouge « An Exception was encountered » et sorties perdues. Les artefacts d'échec
sont retirés ; il ne reste du diff que la vraie correction, la tolérance à l'absence de
`gama_arrivals.csv`.

---

## [2026-08-20] Jeux de calibration `v5` : un seul jour par prompt, doublons écartés

Les jeux gelés de la calibration sont régénérés depuis le run de 24 h du 2026-08-19, avec
deux corrections de fond sur ce que le modèle lit.

**La météo ne se contredit plus dans un même prompt.** Depuis les jeux `v2`, la météo du
départ est tirée dans l'année climatique complète pour ne plus calibrer dans un monde sans
pluie. Mais le bloc persona porte deux autres énoncés météo — l'horizon des créneaux
restants de la journée (« Météo plus tard : après-midi 12 °C… ») et les annotations de
l'agenda glissant (« — pluie prévue ») — qui restaient, eux, ceux du jour du run. Un prompt
pouvait annoncer 18 °C et des averses au départ, puis un après-midi ensoleillé : le modèle
voyait deux jours à la fois. Les trois énoncés viennent désormais du même jour tiré.

**Les répétitions de décisions ne comptent plus deux fois.** Un run de 24 h rejoue les mêmes
trajets le jour simulé suivant, et une reprise à chaud les rejoue une troisième fois. 323
répétitions sur 2 514 décisions ont été écartées au gel ; le manifeste en publie le compte.

**Avant :** 0 % de précipitations en `v1`, puis en `v2`–`v4` une météo de départ pluvieuse
sur un horizon de journée resté sec, et des personas pesant deux fois dans les strates.
**Après :** 44 % des décisions portent des précipitations, l'horizon du jour et l'agenda
suivent le même jour, et chaque décision ne pèse qu'une fois.

La campagne repart sur une branche neuve `ref2`, semée par le prompt système de production
(`expert_chaine`) et non par le prompt naïf d'origine : elle mesure ce que la calibration
gagne **encore** à partir du prompt déjà retenu. Le protocole pré-enregistré est amendé en
conséquence (A8), effectifs et perte de comparabilité compris.

**Le lancement a révélé un troisième défaut, corrigé.** L'état de la boucle génétique
(génération, population, champion, compteur de stagnation) était rangé sous une clé
**globale**, partagée par toutes les campagnes d'un même store. La première passe de `ref2`
a donc repris la trajectoire de `ref1` — génération 11, ses neuf individus, son champion —
sans jamais semer la graine déclarée, et à une mesure de val d'une convergence héritée. La
clé porte désormais la branche, un store portant l'ancienne refuse de démarrer jusqu'à ce
qu'on lui dise à quelle campagne elle appartient, et les rapports de génération sont rangés
par branche au lieu de s'écraser. Amendement A9.

---

## [2026-08-20] La page de synthèse reconnaît un run repris à chaud

La page principale comptait deux fois les décisions d'un run relancé avec
`make run OFFLINE=1 CONT=1`. La reprise rejoue le jour simulé depuis t0 **dans le même
dossier d'expérience** : `moves.csv` porte alors deux lignes par décision, une par
tentative, toutes deux datées du même jour simulé — la coupe au premier jour simulé ne
les sépare donc pas. Le jeu d'évaluation commun ne retient plus que la tentative la
plus récente, et la page annonce qu'elle a lu un run repris ainsi que le nombre de
lignes écartées, comme elle le faisait déjà pour la coupe au jour simulé. La page par
modèle appliquait déjà cette lecture ; les deux sont désormais d'accord.

Le dédoublonnage se fait sur le triplet (personne, activité, **jour simulé**). Sans le
jour, la décision du jour 1 et sa répétition du jour 2 — celles que la coupe au premier
jour simulé est là pour écarter — passeraient pour deux tentatives de la même décision,
et la décision disparaîtrait du score au lieu d'y entrer une fois.

Aucun chiffre publié ne bouge : le run épinglé n'a pas été repris, et la régénération
donne un `data.json` identique à la virgule près.

**Avant :** un run repris affichait 24,43 — 1 469 lignes en doublon, 282 décisions
comptées deux fois — sans que rien sur la page ne le signale.
**Après :** le même run affiche 24,09, et la page dit qu'elle a écarté 1 469 lignes de
reprise. L'écart de 0,34 point est du même ordre que les gains que la calibration
cherche à mesurer.

---

## [2026-08-20] Le score d'un run se ventile par modèle

Un run qui fait tourner plusieurs modèles produisait un seul score : la page de
synthèse agrège le run entier et ne regarde pas quel fournisseur a décidé quoi.
`make model-compare RUN=…` publie désormais une page par run
(`docs/synthesis/models/<run>/`) qui reprend la loss et le lecteur de la page
principale, mais découpe le journal modèle par modèle, isole les trajets à
itinéraire unique, et affiche la santé du run à côté de son score. Aucun appel LLM :
tout est relu dans `moves.csv`.

Trois garde-fous accompagnent le découpage. Un **test de permutation** dit si l'écart
entre deux modèles survit au bruit de découpage — un sous-ensemble plus petit gonfle
mécaniquement les divergences par strate. Un **contrôle de comparabilité** vérifie que
les modèles ont reçu des personas semblables (âge, distance, genre, occupation, motif,
nombre de modes proposés). Et la **reprise à chaud** est reconnue : un run repris avec
`CONT=1` porte deux fois les mêmes décisions, la page mesure la tentative la plus
récente et publie les deux lectures côte à côte.

**Avant :** « ce run est à 24,1 » — sans moyen de savoir que deux modèles s'y
partageaient les décisions avec 5 points d'écart entre eux.
**Après :** le classement des modèles est mesuré, testé contre le bruit, et la part des
décisions qui n'a jamais atteint un modèle est affichée en regard du score.

---

## [2026-08-19] La règle de chaîne passe au prompt système, la ligne « Vos véhicules » disparaît

Mesuré sur le premier run avec anticipation : la ligne « votre vélo est au domicile,
avec vous » agissait comme une invitation et gonflait la part vélo de +5,5 points
(écart à la référence EMC² : +13,8 → +19,6). La ligne est supprimée du bloc persona ;
la règle de chaîne vit désormais dans le prompt système (nouvelle variante
`expert_chaine`, seed `expert`, promue via `active:`) : « en cas d'utilisation d'un
véhicule personnel, pense au stationnement et aux déplacements du reste de la journée,
jusqu'au retour au domicile ». L'agenda glissant et la météo du jour restent dans le
bloc persona ; la disponibilité des véhicules reste portée par le jeu d'options (verrous).

**Avant :** le prompt énonçait la position des véhicules par persona, avec un effet
de saillance mesurable sur le vélo.
**Après :** consigne de chaîne générique côté système, zéro mention de véhicule dans
le bloc persona ; le changement de variante isole automatiquement le cache de décisions
(nouveau checksum).

---

## [2026-08-19] Arrêt à chaud et reprise d'un run : `make stop-run` / `make run CONT=1`

Un run interrompu (plantage, arrêt volontaire, machine éteinte) repartait toujours
de zéro : nouveau répertoire d'expérience, journaux et métriques repartis à vide.
`make stop-run` arrête proprement la simulation (GAMA + launcher headless) en
laissant la pile en place, et `make run OFFLINE=1 CONT=1` reprend **dans le même
répertoire** : moves.csv et app.log s'appendent, state.json et les checkpoints de
population sont retrouvés, les données Grafana/Prometheus/Redis sont conservées.
La simulation repart à t0 du jour simulé (GAMA ne gèle pas son état en plein
trajet) mais les caches rendent le rattrapage quasi instantané et sans quota LLM.

**Avant :** après l'OOM GAMA du run 2026-08-19_11_01, la relance a créé un
nouveau run et re-déroulé la journée dans un répertoire vierge.
**Après :** `make run OFFLINE=1 CONT=1` aurait repris dans le même répertoire,
journaux et métriques continus.

---

## [2026-08-19] Les agents anticipent leur journée au moment du choix de mode

Le choix modal restait myope : au départ du matin, l'agent ignorait ses déplacements
de l'après-midi — partir à pied le privait de voiture toute la journée sans qu'il ait
pu le peser. Le bloc persona du prompt contient désormais l'agenda glissant des trajets
restants (heure, motif, distance), la position de ses véhicules (« votre vélo est avec
vous et devra être revenu au domicile ce soir »), et la météo des tranches restantes de
la journée. Le choix reste trajet par trajet et les trois verrous de chaîne (ticket 008)
restent le filet de sécurité — le bloc informe, il ne contraint pas.

Le bloc agenda/véhicules n'est généré que pour les agents qui ont un véhicule à
chaîner (jamais pour les passagers) ; la météo du jour est montrée à tous. La colonne
`Anticipation` de `moves.csv` trace ce que chaque prompt contenait (segmentation A/B),
et la signature du bloc entre dans la clé du cache de décisions : deux anticipations
différentes ne peuvent pas se servir mutuellement une décision. Désactivable par
`agenda_anticipation_enabled: false` (rétablit le prompt myope à l'identique, cache
compris). Référence « avant » : run sain `2026-08-19_09_40` — 25,8 % des journées-agents
y subissaient un verrou de sortie sur un trajet > 2 km (mesure ticket 014, à faire baisser).

**Avant :** l'agent choisissait chaque trajet sans voir la suite de sa journée ; les
conséquences (vélo resté au bureau, voiture indisponible) étaient subies aux trajets suivants.
**Après :** le LLM voit l'agenda restant, la position des véhicules et la météo à venir
au moment de chaque choix.

---

## [2026-08-19] `make synthesis` rapatrie le store cloud avant de générer la page

La page de synthèse se générait sur une copie locale de `calibration_cloud.db` qui
n'était rafraîchie qu'à la main : le volet calibration pouvait refléter une campagne
vieille de plusieurs semaines sans le signaler. `make synthesis` commence désormais
par rapatrier le store depuis la VM cloud ; si la VM est injoignable, une alarme
explicite indique la date de l'instantané local utilisé. `make synthesis PULL=0`
saute le pull (travail hors-ligne).

**Avant :** la page pouvait montrer une campagne cloud figée au dernier `pull-db` manuel (ex. : 9 nœuds `ga1` du 2 août alors que la VM en portait 47).
**Après :** chaque `make synthesis` reflète l'état réel du store cloud (tuile « Campagne cloud » : 331 nœuds, 385 évals), ou avertit `[ALARME]` s'il ne peut pas.

**Limite connue :** la trajectoire du volet calibration se lit sur les évals `train` ;
la campagne génétique (ticket 009) évalue ses nœuds sur des jeux `rank`/`screen`,
que la page ne trace pas. Le store est à jour, mais les champions GA restent
invisibles de la courbe tant qu'ils n'ont pas d'éval `train` (ou que la page
n'apprend pas à lire le jeu `rank`).

---

## [2026-08-19] `make analysis` utilise le venv du projet

La cible `analysis` lançait `python` du système, qui n'a pas papermill : les quatre
notebooks échouaient systématiquement (`No module named papermill`), même venv activé.
Elle utilise désormais l'interpréteur du venv du projet, comme `dashboard` et `synthesis`,
surchargeable via `make analysis ANALYSIS_PYTHON=/chemin/vers/python`.

**Avant :** `make analysis` échouait avec `No module named papermill` selon le shell appelant.
**Après :** les notebooks tournent avec `llm-agents/.venv/bin/python`, quel que soit l'environnement du shell.

---

## [2026-08-18] Rafraîchissement des providers depuis les quotas réels

`make providers` a resynchronisé `llm_module/config/providers.yaml` avec l'état réel des
fournisseurs. Les deux instances Groq Llama (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`)
sont désactivées : leurs modèles ont disparu du catalogue `/models` de Groq. Un nouveau
provider `google_gemini_3_7_flash` est référencé hors rotation (weight 0, RPD free tier trop
bas). Mistral et les deux instances Cerebras répondent désormais **HTTP 402 (payment
required)** : leurs blocs restent inchangés mais ces capacités sont indisponibles tant que le
free tier n'est pas rétabli.

**Avant :** la rotation croyait disposer de Groq Llama 3.3/3.1 (modèles supprimés côté Groq → erreurs à l'appel).
**Après :** la rotation ne contient que des instances dont le modèle existe réellement ; capacité nominale réduite d'environ 0.4 de weight.

---

## [2026-08-18] make analysis tolère l'absence d'arrivées GAMA

`make analysis` ne plante plus quand le run n'a pas produit `gama_results/gama_arrivals.csv`
(run interrompu, GAMA jamais arrivé au dump des arrivées). Le notebook `pipeline.ipynb`
saute proprement la section retard d'arrivée, et `delays.ipynb` — entièrement dédié aux
arrivées — est ignoré avec un message explicite au lieu de faire échouer toute l'analyse.

**Avant :** `KeyError: 'delay_s'` dans `pipeline.ipynb`, puis `FileNotFoundError` dans `delays.ipynb` ; `make analysis` sortait en erreur sans produire les autres rapports.
**Après :** les trois notebooks exploitables s'exécutent, `delays.ipynb` est marqué `[SKIPPED]` avec le fichier manquant nommé.

---

## [2026-08-18] Le mutateur réfléchit avant d'écrire

Le modèle qui **propose** les mutations de prompt dispose maintenant d'un budget de réflexion
(1024 tokens). Il l'utilise sur les trois chemins où il rédige : mutation ciblée, croisement,
et génération des variants de départ. Le modèle qui **évalue** n'y touche pas.

La raison vient de la littérature : GAAPO (arXiv:2504.07157) compare les LLM employés comme
générateurs de prompts et mesure que les modèles capables de raisonner mènent la validation à
0,68–0,70 là où un généraliste stagne à 0,45–0,50 dès la deuxième génération. Écrire une
mutation suppose de peser une carte de contribution par bloc, des écarts par tranche d'âge et
de motif, un historique de rejets et une liste tabou — le genre de tâche où délibérer paie.

**Avant :** le mutateur répondait au premier jet, sans étape de réflexion.
**Après :** il dispose de 1024 tokens pour raisonner avant de rédiger sa proposition.

Le juge, lui, reste sans réflexion, et c'est délibéré : un modèle qui délibère converge vers la
réponse typique, alors qu'on cherche justement à reproduire la **dispersion** des choix d'une
population. Le réglage n'entre pas dans la clé du cache d'évaluation — aucune des évaluations
déjà payées n'est perdue.

Deux garde-fous, parce que réflexion et réponse se partagent le même plafond de sortie : le
plafond de chaque appel est relevé du montant du budget, et une réponse tronquée lève désormais
une alarme qui nomme la cause avec ses chiffres — au lieu d'échouer sur un obscur « Expecting
value: char 0 ».

Réglages : `mutation_thinking_budget` (0 désactive, -1 laisse le modèle arbitrer),
`mutation_thinking_reserve`.

---

## [2026-08-18] Le biais voiture est comportemental, pas instrumental — mesuré à 6 %

On soupçonnait l'instrument. Les options d'itinéraire montraient une voiture plus rapide
qu'elle ne l'est, et le prompt calibré la choisissait massivement pour des trajets de
800 mètres. La question était : combien de ce travers venait des données fausses, et combien
du comportement du modèle ?

**Réponse : 6 %.** En corrigeant les durées sans toucher au prompt, la sur-représentation de
la voiture sur les trajets de moins d'un kilomètre passe de +32,3 à +30,2 points d'écart à
l'enquête ménages. Deux points sur trente-deux.

La mesure a demandé un jeu de comparaison qui ne diffère de l'original que par **une seule**
variable — mêmes habitants, mêmes trajets, mêmes options en transports collectifs au
caractère près, seules les lignes voiture et vélo réécrites. Sans cette précaution, la
différence n'aurait été attribuable à rien.

**Avant :** « le modèle met les habitants en voiture pour 800 mètres » — lecture suspendue,
faute de savoir si on lui montrait une voiture réaliste.
**Après :** on lui montre une voiture honnête, et il continue. Le constat tient, et il porte
sur le comportement du modèle.

Contre-épreuve : le prompt non calibré ne s'améliore pas davantage (+10,3 → +11,3). Ce n'est
donc pas une résistance propre au prompt optimisé — le modèle lui-même ne réagit pas au coût
de stationnement sur les trajets courts.

Second résultat, sur la même mesure : **l'avance du prompt calibré n'est pas un artefact.**
On craignait qu'une partie de son gain consiste à compenser le défaut, et devienne une double
peine une fois celui-ci corrigé. C'est l'inverse — son avance passe de 7,18 à 9,08 quand
l'instrument devient honnête.

---

## [2026-08-18] Le coût de la voiture dépend maintenant du quartier

Se garer au Capitole et se garer en 3ᵉ couronne ne coûtent pas le même temps. Jusqu'ici le
simulateur appliquait la même valeur partout, ce qui sous-estimait le coût d'usage de la
voiture au centre et le surestimait en périphérie — donc aplatissait précisément la variation
spatiale qu'on cherche à mesurer.

Le temps d'accès et de stationnement suit désormais les couronnes de l'enquête ménages, et
**les deux bouts d'un trajet sont tarifés séparément** : rejoindre son véhicule dépend d'où
l'on part, trouver une place dépend d'où l'on va.

| | rejoindre la voiture | stationner et marcher |
|---|---|---|
| Toulouse | 3 min | 7 min |
| 1ʳᵉ couronne | 2 min | 4 min |
| 2ᵉ couronne | 2 min | 3 min |
| 3ᵉ couronne | 1 min | 1 min |

**Avant :** 6 minutes de temps terminal, partout.
**Après :** 10 minutes pour un trajet interne à Toulouse, 2 minutes en 3ᵉ couronne — et
8 minutes pour venir de la 3ᵉ couronne au centre (accès rural, stationnement de centre).

Effet mesuré sur le prompt calibré : l'écart à l'enquête baisse de près de 3 points. Le
zonage n'a pas été inventé pour l'occasion — c'est celui des couronnes de résidence déjà
utilisées par le journal de déplacements, remonté dans un module partagé pour qu'il n'en
existe qu'une définition.

---

## [2026-08-18] Le mode rapide de génération de prompts est abandonné

Il promettait de reconstruire la base de prompts en minutes au lieu d'heures, sans appeler le
modèle de langage. Il tient cette promesse, mais il produit une base **inutilisable pour
calibrer**, et c'est structurel.

En simulation, un véhicule reste là où on l'a laissé : qui part travailler en bus laisse son
vélo à la maison et ne peut pas rentrer à vélo. Savoir où est le vélo suppose de connaître le
mode choisi au trajet précédent — donc d'avoir interrogé le modèle. Le mode rapide ne
l'interroge pas : la dépendance est circulaire, sans contournement.

Résultat, le vélo est proposé à chaque trajet comme s'il se téléportait. **Mesuré : 34 % de
vélo sur les trajets de moins d'un kilomètre, contre environ 9 % sur une base issue d'une
simulation.**

**Avant :** mode rapide présenté comme la voie normale de régénération.
**Après :** le script refuse de tourner sans confirmation explicite, et le jeu qu'il a produit
porte la mention « inapte à la calibration » dans son manifeste. Il garde deux usages
légitimes : réchauffer les caches d'itinéraires — il calcule exactement les routes dont une
simulation aura besoin — et éprouver un rendu.

Une simulation complète reste donc nécessaire pour produire une base de calibration.

---

## [2026-08-17] La voiture ne payait pas son stationnement, et le vélo non plus

Les options d'itinéraire soumises aux habitants facturaient aux transports collectifs
l'intégralité de leur temps d'accès — la marche jusqu'à l'arrêt, la correspondance, la marche
jusqu'à la destination, détaillées minute par minute — et **rien de visible** à la voiture ni
au vélo. Devant « voiture 7 minutes / bus 13 minutes » pour aller à 1,4 km, choisir la
voiture est un raisonnement correct. Le modèle raisonnait juste sur une réalité fausse.

Le temps de stationnement existait pourtant déjà : 4 minutes pour la voiture, 2 pour le vélo,
ajoutées en silence à la durée du trajet, sans provenance et sans jamais être montrées. Ce
n'était donc pas leur magnitude qui était fausse, c'était leur invisibilité — face à des
options en transports collectifs décomposées pas à pas.

Le temps d'accès et de stationnement est désormais un **paramètre documenté**, chaque valeur
avec sa source et son lien (tables de *terminal times* de la modélisation des déplacements,
littérature sur la recherche de place, enquêtes Cerema). La valeur du vélo est déclarée **non
sourcée** — aucune référence chiffrée n'existe pour un vélo personnel — plutôt que maquillée
avec un chiffre de vélo en libre-service. Et les habitants voient maintenant la décomposition,
comme ils voient celle des transports collectifs.

**Avant :**
```
- [4] car: Durée estimée : 6 minutes. Distance : 944 m.
```
**Après :**
```
- [4] car: Temps de trajet : 8 minutes, dont 6 minutes d'accès et de stationnement. Distance : 944 m.
    · Rejoindre la voiture : 2 minutes.
    · Conduite : 2 minutes.
    · Stationnement et marche jusqu'à 'leisure' : 4 minutes.
```

Sur ce déplacement de 900 mètres, la voiture passe de meilleure option (6 min) à égalité avec
le bus (8 min), et l'habitant voit que 6 de ses 8 minutes ne sont pas de la conduite. Les
options en transports collectifs et à pied ne changent pas d'une seule minute — leur temps
d'accès était déjà compté, l'ajouter deux fois aurait été le défaut inverse.

Le vélo, lui, garde exactement sa durée : ses 2 minutes terminales étaient déjà là, elles sont
simplement nommées. Si les parts vélo bougent, ce sera par la seule mise en évidence.

**Deux caches ne pouvaient pas voir ce changement**, et l'un était dangereux : le cache de
décisions est indexé sur les lignes et les arrêts d'un itinéraire, pas sur ses durées. Il
aurait rejoué indéfiniment des décisions prises sur l'ancienne réalité, sans qu'aucun message
ne le signale. Les deux clés portent désormais une version des données d'itinéraire.

---

## [2026-08-17] Régénérer la base de prompts sans relancer la simulation

Corriger la construction des itinéraires imposait jusqu'ici de rejouer 24 heures de
simulation pour reconstituer la base de prompts de la calibration — soit un budget de modèle
de langage entier, alors que **les itinéraires proposés ne dépendent pas de ce que le modèle
choisit** : le calculateur de trajets et le réseau routier suffisent à les construire.

Un mode rapide reconstruit donc la base directement depuis la population, en **zéro appel au
modèle** : quelques minutes au lieu de plusieurs heures. Le mode simulation reste intact et
demeure la seule voie quand la mémoire des habitants doit être exploitée — les deux
producteurs alimentent la même chaîne de gel, et le manifeste enregistre lequel a servi.

**Avant :** toute correction des itinéraires = un run complet, plusieurs heures, budget LLM
entier consommé pour produire des prompts.
**Après :** `make prompt-base` — quelques minutes, aucun appel au modèle. Le run complet
reste disponible pour ce qu'il apporte seul : la mémoire court et long terme.

Deux limites du mode rapide sont écrites dans le manifeste du jeu produit plutôt que laissées
à découvrir : pas de section mémoire, et la chaîne de véhicules n'est pas rejouée (savoir où
un vélo est garé suppose de connaître le mode choisi au trajet précédent, donc d'avoir
interrogé le modèle). Trois réglages jusqu'ici implicites deviennent au passage explicites et
consignés — la graine du mélange des options, l'ordre d'énumération, l'origine de la météo —
sans quoi deux générations de la même base ne donnaient pas le même texte.

---

## [2026-08-17] Le chiffre publiable de la calibration ne mesurait qu'un sixième de lui-même

La campagne de référence a été arrêtée et finalisée. Sa première finalisation a rendu un
résultat **faux** : les cinq découpages par tranche d'âge, occupation, genre, motif et
distance sont sortis « non mesurés » sur le jeu de test, remplacés chacun par la pénalité
maximale des deux côtés de la comparaison — donc annulés dans l'écart. Le gain annoncé ne
portait que sur la distribution globale.

La cause : la table qui associe chaque habitant simulé à ses caractéristiques était
construite sur les jeux d'entraînement et de validation seulement. Les autres jeux
intermédiaires en sont des sous-ensembles, si bien que le défaut restait invisible — sauf
sur le jeu de test, le seul strictement disjoint, et le seul qu'on ne consulte qu'une fois
dans la vie d'une campagne.

Les décisions brutes, elles, étaient intactes : le score a pu être recalculé **sans
réinterroger le modèle**. Le gain réel est plus de deux fois supérieur à celui qui avait été
annoncé, et il est significatif.

**Avant :** écart mesuré −3,41, portant en réalité sur un seul des six termes.
**Après :** écart réel **−7,13**, intervalle de confiance à 90 % [−10,37 ; −4,35] sur
259 habitants appariés — soit 4,4 fois le seuil de détection annoncé avant la mesure.

Une réserve accompagne ce résultat : toutes les dimensions s'améliorent **sauf la
distance**, qui se dégrade. C'est exactement l'axe sur lequel la recherche n'avait aucune
direction disponible et sur lequel les données d'itinéraire sont biaisées — les deux
constats du jour, confirmés ici sur un jeu tenu à l'écart de toute la campagne.

---

## [2026-08-17] Deux garde-fous de la calibration étaient débranchés

Deux protections décrites dans la documentation et le protocole existaient bel et bien dans
le code, avec leurs tests — mais **rien ne les appelait**. La campagne de référence a tourné
onze générations sans qu'aucune des deux ne s'exécute une seule fois.

La première grave l'empreinte de la configuration au démarrage et refuse de reprendre une
campagne sous un instrument différent : changer de modèle d'évaluation au douzième jour était
jusqu'ici indétectable. Elle refuse désormais, en nommant le champ qui a changé ; l'assumer
explicitement reste possible, mais l'écart est alors enregistré et signalé.

La seconde enregistre, sur chaque mutation, le bras expérimental qui l'a produite — sans quoi
on ne peut plus dire après coup quelle variante de l'algorithme a proposé quoi. Les onze
points d'écriture le renseignent maintenant. L'import de campagnes anciennes, lui, continue
délibérément à ne rien inscrire : leur régime est réellement inconnu, et lui en inventer un
serait pire que de l'ignorer.

**Avant :** deux garanties annoncées, zéro exécution — le registre de configuration était
vide et la colonne de régime nulle sur 106 mutations.
**Après :** les deux sont armées, avec des tests qui vérifient l'appel et non plus seulement
la mécanique.

Aucun dégât sur la campagne écoulée : son instrument n'a pas bougé, c'est vérifiable dans le
store. Ce qui manquait était la garantie, pas la propriété.

---

## [2026-08-17] La calibration peut enfin retirer et ajouter des phrases

La recherche de prompt ne savait que **réécrire** des phrases existantes : elle n'a jamais
retiré ni ajouté un seul bloc de toute la campagne de référence. Le coût était mesurable —
le diagnostic du champion signalait depuis cinq générations qu'une de ses phrases
*dégradait* le score, la version sans cette phrase était déjà évaluée et en cache, et rien
ne pouvait la retenir comme candidate. Deux opérateurs ferment le trou : le **retrait**
d'une phrase mesurée nuisible (gratuit — aucun appel au modèle, et la version raccourcie
est déjà évaluée) et la **greffe** d'une phrase neuve qui laisse tout le reste intact.

Un dixième axe de diversification est ajouté, l'**échelle du trajet** : aucun des neuf
précédents ne portait sur la longueur du déplacement, alors que c'est là que la simulation
se trompe le plus — sur les trajets les plus courts, elle met la moitié des habitants en
voiture quand l'enquête en met moins d'un cinquième. L'axe agit par le mécanisme (sortir un
véhicule coûte le même effort quel que soit le trajet, donc pèse d'autant plus qu'il est
bref) et non par un seuil chiffré, qui reviendrait à écrire la réponse attendue dans le
prompt — et serait de toute façon rejeté avant évaluation.

**Avant :** la recherche explorait à structure de prompt figée ; une phrase mesurée
nuisible y restait indéfiniment, et aucune direction ne visait la longueur du trajet.
**Après :** elle peut raccourcir, allonger, et diversifier sur l'échelle du déplacement.

La campagne en cours n'est **pas** modifiée : elle arrive à sa règle d'arrêt et changer son
espace de recherche en route rendrait cet arrêt ininterprétable. Les opérateurs valent pour
la campagne suivante ; la limite correspondante est inscrite au protocole (amendement A4).

---

## [2026-08-13] Fin du spam nocturne du watchdog de calibration

Pendant une veille quota (état attendu : les tokens sont épuisés, la campagne attend le
renouvellement), le chien de garde envoyait la même alarme « registre immobile » sur
Discord à chaque passe de 2 h — jusqu'à 5-6 messages identiques par nuit. Les alertes
passent à front montant : la première part toujours, les répétitions à l'identique se
taisent, un rappel quotidien porte l'ancienneté d'une alarme durable, et une levée 🟢 est
notifiée au retour au sain. La détection, elle, est inchangée : `doctor` sort toujours en
code 2 et l'arrêt d'une passe figée reste inconditionnel.

**Avant :** une nuit de veille quota = 5-6 alertes 🚨 identiques.
**Après :** une seule alerte à l'entrée en veille, une levée 🟢 à la reprise ; rappel
au-delà de 24 h si l'alarme persiste.

---

## [2026-08-12] Le biais vélo/marche est mesuré, et on sait quelle part le prompt peut corriger

L'écart aux parts modales toulousaines était connu qualitativement — « le vélo est
surestimé, la marche sous-estimée ». Il est maintenant chiffré par strate, sur les mêmes
2 830 décisions que la politique statistique entraînée sur l'enquête, ce qui permet de
séparer deux choses qu'on confondait.

**Avant :** un écart global attribué au prompt, sans savoir ce qu'un prompt pouvait en
récupérer.
**Après :** marche −16,7 points, vélo +12,0, voiture juste à 0,2 point près — et surtout,
les causes sont identifiées. **28 % des décisions n'offrent qu'un seul itinéraire**, et
neuf fois sur dix c'est le **verrou de retour de véhicule** : l'agent qui a pris son vélo
le matin doit le ramener le soir. Ces trajets ne sont donc pas des contraintes subies mais
les **échos** d'un choix fait un trajet plus tôt — le dispositif ne dilue pas le biais du
prompt, il le double. S'y ajoutent une simulation qui produit **deux fois moins de trajets
de moins d'un kilomètre** que la réalité toulousaine, là où trois déplacements sur quatre
se font à pied. Sur les seules décisions offrant un choix réel, le modèle statistique
retombe sur la cible (4,5 % de vélo pour 4,1 attendus) — l'écart restant, **+8,6 sur le
vélo et −17,6 sur la marche, est bien celui du prompt**.

Un défaut à corriger au passage : **88 retours forcés descendent d'une décision que le
scoring exclut** (le repli quand le LLM n'a pas répondu). La décision est écartée, sa
conséquence est comptée — l'exclusion doit suivre la chaîne du véhicule.

Le défaut central n'est pas un niveau mais une **absence de réponse à la distance** :
l'excès de vélo est constant de +9 à +16 points sur toutes les bandes, jusqu'à 11 % de
vélo sur les trajets de 10 à 20 km — là où l'enquête en compte 2 %. Sur les trajets de
moins d'un kilomètre, où trois Toulousains sur quatre marchent, l'agent choisit autre
chose une fois sur deux.

Mesure, tableaux par âge, occupation, motif, distance et genre, et script de rejeu (zéro
appel LLM) archivés avec les autres mesures de la calibration.

---

## [2026-08-12] Calibration : deux passes ne peuvent plus écrire ensemble dans le store

Les deux passes quotidiennes de la campagne se partageaient un même fichier de campagne
sans autre protection que l'écart entre leurs horaires de déclenchement. Comme une passe
a le droit de durer jusqu'à sept heures, rien n'empêchait la seconde de démarrer pendant
que la première écrivait encore.

Une passe prend désormais un **verrou exclusif** sur le store avant tout appel LLM. Si
le store est occupé, elle attend, réessaie, puis renonce proprement sans rien écrire ni
consommer de quota — et le dit dans le journal. L'heure de déclenchement reste tirée au
sort à la seconde près : l'aléa sert à étaler la charge, plus à garantir la correction.

**Avant :** deux passes concurrentes possibles dès qu'une passe débordait de sa fenêtre,
avec écriture simultanée dans le même SQLite (mode d'échec observé le 11 août).
**Après :** séquentialité garantie par le noyau ; une passe cédée est journalisée, jamais
silencieuse.

Le protocole pré-enregistré gagne au passage deux précisions demandées en relecture : la
**provenance du prompt de départ** (travaillé à la main avant la campagne, ce qui rend la
comparaison plus exigeante) et une section **usage prévu et limites d'usage** — ce que le
résultat n'autorisera pas à faire, quelle que soit sa significativité.

---

## [2026-08-11] Calibration : la compaction ne plante plus faute de point de comparaison

La passe de compaction (« retirer les phrases inutiles tant que le score ne se dégrade
pas ») compare chaque variant raccourci au prompt courant, en relisant la mesure déjà
stockée de ce dernier. Quand cette mesure n'existe pas sous le régime d'évaluation en
cours — ce qui arrive à la reprise d'une campagne après un changement de protocole, un
cas que le démarrage signale déjà — la passe partait quand même : elle **payait une
évaluation par phrase candidate**, puis s'interrompait sur une erreur technique, en fin
de campagne, après plusieurs heures de travail.

Elle s'abstient désormais **avant de dépenser quoi que ce soit**, et le dit à voix
haute au lieu de passer pour « rien à compacter ». Si le point de comparaison venait à
manquer en cours de passe, la phrase est simplement conservée (refus prudent) plutôt
que de faire tomber la campagne.

**Before :** compaction finale → N évaluations payées → `AttributeError`, passe perdue.
**After :** « compaction sautée : aucune éval du prompt courant sous la clé … » —
0 évaluation payée, prompt intact, campagne terminée normalement.

---

## [2026-08-11] Calibration : la suite de tests couvre enfin ce qui décide de la dépense

La calibration de prompt avait 565 tests, tous concentrés sur ses formules — et **un
quart de son code jamais exécuté en test**. Ce quart-là n'était pas du détail : c'était
la CLI (les commandes réellement lancées par le Makefile et systemd), les verrous de
démarrage, le dashboard, et l'envoi des rapports. La suite passe à **1001 tests** et
couvre **97 % du code du module** (76 % avant), en ciblant d'abord les endroits où une
régression coûte des heures de quota plutôt que quelques décimales.

**Les verrous de démarrage sont désormais armés en test.** Quatre gardes protègent le
lancement d'une campagne : provider absent de `providers.yaml`, fuite du jeu de test
dans le jeu d'entraînement, modèle d'évaluation en alias flottant, clé d'API de mutation
manquante. Aucun n'avait de test : rien ne disait s'ils pouvaient se déclencher. C'est
exactement le défaut qui avait laissé passer quatre jours de panne silencieuse — un
garde jamais éprouvé est un garde dont on ignore l'état. Chacun a maintenant son test
d'armement *et* son test de silence (un garde qui bloque tout est aussi inutile qu'un
garde muet : la reprise d'une branche déjà commencée n'est jamais refusée).

**Before :** `calibrate run`, `ga`, `reeval`, `digest`, `doctor`, `finalize` n'étaient
exercées par aucun test — un défaut ne se voyait qu'en production, sur la VM.
**After :** chaque commande a ses tests de bout en bout, y compris ses sorties
anormales : quota épuisé, mutateur en panne, campagne terminée sans rien avoir calibré.

**Le dashboard est testé en le rendant vraiment.** La couche de lecture était pure et
testée, l'interface ne l'était pas du tout : une vue pouvait lever à chaque ouverture
sans qu'un test s'en aperçoive. Les sept vues sont désormais rendues pour de vrai (dans
le process de test, sans serveur ni navigateur), sur un store peuplé *et* sur des
données partielles. La régression « il fallait deux clics pour changer de vue » a son
test de non-régression, et la seule action qui écrit dans le store — l'import depuis
l'onglet Maintenance — est vérifiée verrouillée tant que la case de confirmation n'est
pas cochée.

**Aucun test ne peut consommer de quota ni notifier.** Les quatre frontières vers
l'extérieur (appels Gemini de mutation et de seeding, adaptateur d'évaluation, SMTP du
canal mail) sont franchies par des doubles, et l'URL du webhook Discord est retirée de
l'environnement de tous les tests. Lancer la suite sur la machine qui détient les
secrets ne poste rien et ne dépense rien.

**Nouvelle règle vérifiée partout : « rien à mesurer » n'est pas un score parfait.**
Dans ce projet, l'absence de mesure produit 0.0 — c'est-à-dire le meilleur score
possible. Un module de tests dédié vérifie, un par un, que chaque trou (jeu vide,
référence absente, journal tronqué, ligne illisible) rend la perte maximale ou un refus
explicite, jamais un zéro flatteur.

**`make coverage`** mesure la couverture et échoue sous 95 % : un chemin nouvellement
écrit et non testé se voit à l'ajout, plus six mois plus tard.

---

## [2026-08-11] Calibration : la boucle recommence à avancer

Trois mécanismes de la boucle de calibration se refermaient sur elle : elle consommait
ses itérations sans jamais rien mesurer, tuait ses meilleures pistes avant de les
regarder, et enregistrait comme des faits des décisions qu'elle disait exploratoires.
La branche `7` en donne la mesure : **38 itérations, zéro acceptation, 3 mesures
complètes payées sur 38 mutations proposées.**

**L'archive des impasses ne se vidait jamais.** Une proposition trop proche d'une
tentative déjà rejetée est écartée sans payer d'évaluation — c'est le bon réflexe, et
l'entrée devait redevenir jouable « au bout d'un moment ». Sauf que « un moment » était
compté en *acceptations*, alors qu'une entrée naît à chaque *rejet* : tant que rien
n'était accepté, rien n'expirait, et l'archive n'a fait que grossir jusqu'à recouvrir
tout l'espace des propositions. Plus une seule évaluation, donc plus une seule
acceptation, donc plus aucune expiration. Le délai se compte désormais en itérations —
un compteur qui avance quoi qu'il arrive — et une alarme part si cinq propositions
d'affilée sont écartées ainsi.

**Before :** 36 impasses mémorisées, toutes datées de la même échéance impossible ;
plus rien n'était évalué après la première.
**After :** l'archive se stabilise autour d'une dizaine d'entrées et se renouvelle ;
une piste écartée redevient jouable après quelques tours.

**Le pré-filtre éliminait 87 % des pistes sur un coup d'œil.** Pour ne pas payer
l'évaluation complète d'une piste sans avenir, chaque essai est d'abord jugé sur un
quart des personas. Le verdict tombait sur une comparaison ponctuelle, sans la moindre
marge d'incertitude : « pas mieux » valait « éliminé ». Sur 38 mutations, **33 sont
mortes là, dont 8 pour un écart si petit que l'autre chemin du même programme les
aurait explicitement gardées**. Or les deux erreurs ne se valent pas : garder une piste
médiocre coûte du calcul, jeter une bonne piste coûte une amélioration qu'on ne
retrouvera jamais. Le pré-filtre n'écarte plus qu'une piste dont la probabilité d'être
une amélioration tombe sous 20 %, et s'abstient franchement quand l'échantillon est
trop petit pour trancher.

**Before :** un essai à `−0,3` point du prompt courant sur un quart des personas était
abandonné.
**After :** il poursuit ; seul l'essai manifestement sans espoir s'arrête là.

**Le quart de personas était toujours le même.** C'étaient littéralement les premiers de
la liste, à toutes les itérations et pour tous les candidats — avec le risque qu'une
catégorie entière (une tranche d'âge, un motif de déplacement) y soit sur- ou
sous-représentée, et que deux prompts soient comparés sur des publics différents.
L'échantillon est désormais tiré une fois par campagne, équilibré sur les mêmes
catégories que celles que la note agrège : sur une population réaliste de 608 personas,
l'écart maximal d'une catégorie à son poids réel tombe de **6,4 points à 0,3**. Les
mesures partielles sont en outre archivées sous une clé qui nomme l'échantillon, pas
seulement sa taille : une ancienne mesure ne peut plus être resservie comme comparable
à une nouvelle.

**Le niveau d'exigence baissait au début de la campagne.** Le seuil de preuve exigé
pour retenir une amélioration était assoupli en début de course, au nom de
l'exploration : de 90 % de confiance à **55 %** — quasiment plus de contrôle du tout,
au moment précis où la campagne écrit le plus. Or une acceptation n'a jamais rien de
provisoire ici : elle déplace le meilleur score, récompense l'opérateur qui l'a
produite, entre en bibliothèque, décale les délais d'expiration et peut déclencher une
passe de raccourcissement du prompt. Une décision que le système enregistre comme un
fait ne peut pas être dite « exploratoire ». Le seuil est désormais **fixe à 90 %**.
L'exploration reste possible, mais là où elle appartient : dans la tolérance au
déplacement, pas dans le niveau de preuve.

**Côté campagne génétique**, le champion sortant reprenait sa place en écrasant
silencieusement un survivant — deux fois par génération, sans une ligne de journal.
Quand l'objet même de l'étude est l'opérateur de sélection, le corrompre en silence
rend la campagne indéfendable. Le champion est maintenant une contrainte donnée à la
sélection, appliquée en un seul endroit, et toute éviction qui en découle est nommée
dans le journal et distinguée dans l'historique. Enfin, les tentatives de croisement
rejouaient toutes le même couple de parents, garantissant des doublons : elles
parcourent désormais les couples disponibles.

---

## [2026-08-11] Calibration : un dispositif enfin capable de conclure

Une analyse de puissance vient d'établir que la campagne de calibration **ne pouvait pas
conclure**, quelle que soit la qualité du prompt trouvé. Le jeu de test comptait 132
personas et le jeu de validation 127 — deux jumeaux trop petits. La plus petite différence
que le dispositif savait détecter valait **2,27 points**, pour un effet attendu de **2,12**.
Autrement dit : même une calibration parfaite aurait rendu « non significatif ». Le défaut
tenait à l'effectif, pas au calcul — changer d'estimateur ne le corrigeait pas.

Trois corrections, livrées ensemble parce qu'elles se tiennent.

**Le découpage des jeux passe de 70/15/15 à 50/20/30.** Le partage 70/15/15 vient d'un monde
où le jeu d'apprentissage commande la qualité et où mesurer coûte peu. Ici c'est l'inverse :
le jeu d'entraînement est réévalué à chaque itération, chaque ablation, chaque essai — son
effectif multiplie toute la facture — tandis que le jeu de test n'est évalué qu'une ou deux
fois dans la vie d'une campagne. L'agrandir est donc quasi gratuit, et rétrécir
l'entraînement **fait baisser le coût**. Les jeux `v3` sont gelés ; `v2` reste intact.

**Avant :** entraînement 608 personas · validation 127 · test 132 → différence détectable
**2,27** (> effet attendu), ~62 requêtes par évaluation d'entraînement
**Après :** entraînement 430 · validation 178 · test 259 → différence détectable **≈ 1,62**
(< effet attendu), ~44 requêtes par évaluation d'entraînement

La population n'a pas changé d'un persona : les jeux `v3` sont un **repartitionnement** des
fichiers gelés de `v2`, pas une régénération. C'était la condition pour que les chiffres de
l'analyse de puissance restent valables. Le jeu de criblage, défini en tranches absolues,
garde exactement les mêmes personas — son coût est inchangé. Et le petit jeu de classement du
génétique doit désormais **prouver** qu'il conserve au moins 30 personas : en deçà, le gel est
refusé, parce que classer sur moins que ça n'est plus classer mais tirer au sort.

**Le champion n'est plus élu parmi cinquante candidats, mais parmi trois.** C'est le point le
plus grave, découvert en dernier. Depuis que la sélection finale repose sur le jeu de
validation, elle rencontre un piège classique : choisir le meilleur parmi K candidats
surestime mécaniquement son mérite, d'autant plus que K est grand. Avec la dispersion mesurée
sur ce jeu, désigner l'argmin parmi une cinquantaine de prompts gonfle le résultat d'environ
**3,9 points** — presque le double de l'effet recherché. Le « champion » pouvait donc être
intégralement du bruit.

**Avant :** le meilleur score de validation sur l'ensemble du registre était publié
**Après :** trois finalistes sont d'abord désignés sur l'entraînement (évaluations déjà
payées, donc gratuit), puis la validation ne départage que ces trois-là — biais ramené à
≈ 2,0 point. Le nombre de finalistes est **figé à trois dans le code** : un garde-fou qu'on
peut desserrer après avoir vu les résultats n'est plus un garde-fou.

Le bilan de fin de campagne dit maintenant **parmi combien** de candidats le champion a été
élu, lesquels étaient en lice, et publie l'**écart entre son score de validation et son score
de test** — le témoin honnête de ce qui reste de biais. Un prompt bien meilleur là où on l'a
choisi qu'ailleurs, ça se voit et ça se dit. Les prompts qui ont purement **supprimé** un mode
de transport sont par ailleurs écartés d'office de la course au titre.

**La version des jeux entre dans la clé du cache d'évaluation.** Une évaluation sur
`v1/train` et une évaluation sur `v2/train` partageaient jusqu'ici la même entrée de cache,
alors qu'elles portent sur des populations différentes : le nom du jeu était mémorisé, sa
version non. Le défaut restait latent tant que la population ne bougeait pas ; avec l'arrivée
de `v3`, il devenait certain. **Conséquence assumée : le cache existant est invalidé et la
campagne repart sur une base neuve.** Rien n'est détruit — les décisions brutes restent
lisibles et rejouables.

**Trois filets posés au passage.** Un score construit sans aucune mesure valait encore `0,00`,
c'est-à-dire la note **parfaite** ; il vaut désormais la pire note possible, très au-delà de
tout score réel — on ne peut plus gagner un classement en ne mesurant rien. Une décision peut
enfin emporter jusqu'en base la **référence du déplacement** dont elle provient, ce qui ouvre
la voie à un scoring au bon grain pour les personas qui font plusieurs trajets. Et un rejet
« faute d'effectif suffisant » se distingue maintenant explicitement d'un rejet « faute de
résultat » : ne pas avoir pu mesurer n'est pas avoir mesuré une absence d'effet.

Enfin, `calibrate rescore` applique rétroactivement le retrait de la pénalité de mode absent
sur tout l'historique — un simple calcul, zéro appel au modèle — et il est rejouable sans
risque de soustraire deux fois.

---

## [2026-08-11] Calibration : ce que « meilleur » veut dire

Le classement des prompts reposait sur une loss dans laquelle **l'absence de donnée
était indiscernable d'une donnée** — et le biais penchait toujours du côté flatteur.
Le composite est une perte : `0.00` est le score **parfait**. Or plusieurs chemins du
code rendaient `0.00` non pas parce que la mesure était bonne, mais parce qu'il n'y
avait rien à mesurer. Sur le store, neuf évaluations importées **sans aucune décision**
se recalculaient à `0.00` pile. Sept évaluations de criblage portant sur 8 à 35
personas décrochaient une note parfaite sur la tranche d'âge — aucune tranche n'était
assez peuplée pour être regardée. La plus petite d'entre elles, **8 personas et quatre
dimensions offertes**, était le **meilleur prompt du jeu de criblage**.

Cinq corrections liées, livrées ensemble parce qu'elles se répondent : la valeur d'un
échec change les effectifs, qui changent ce qu'on estime.

**La pénalité de mode absent quitte le score.** Elle valait `5 × la part de référence`
du mode oublié. Comme la référence est libellée en pourcents, un mode oublié coûtait
jusqu'à 275 points, face à des dimensions de qualité valant 2 à 25. Mesuré sur le
store : **130 points sur un composite de 289, soit 45 % de la note d'un prompt**. Ce
n'était plus un terme de la loss, c'était la loss. Elle est désormais **calculée,
stockée et affichée** — mais de poids nul, exactement comme la pénalité de longueur
l'an dernier. Le jugement qu'elle portait légitimement devient un **critère de
recevabilité** en tout ou rien : un prompt qui accorde une masse **exactement nulle** à
un mode que la référence estime à 1 % ou plus n'est pas recevable, point. Aucune
évaluation passée n'est à jeter : le nouveau score se déduit de l'ancien par une simple
soustraction, sans rappeler le modèle une seule fois.

**Une non-mesure devient la pire note, plus la meilleure.** Une dimension qu'on n'a pas
pu mesurer — colonne manquante, aucune strate assez peuplée, référence absente — vaut
désormais la **perte maximale** de son axe, et la liste des dimensions non mesurées
voyage à côté du score, avec l'effectif de chacune. Le journal d'évaluation dit
maintenant sur quoi il a compté (`n=608 personas · masse/persona=1.000 · Autre=0.4 %`)
et lève une alarme dès qu'une dimension n'a pas été regardée.

**Mais on n'élimine plus un candidat qu'on n'a pas su mesurer.** C'est la règle jumelle,
et l'inverse de la précédente : sévère quand il faut produire une note, prudent quand il
faut écarter quelqu'un. Sinon on remplace un biais optimiste par un biais pessimiste,
plus difficile à voir.

**Un test statistique exige au moins 30 agents appariés.** Le seuil porte sur les
agents présents des deux côtés de la comparaison — jamais sur les lignes : le jeu
d'entraînement compte 3 024 lignes pour 608 personnes, et compter les lignes
fabriquerait une précision cinq fois trop belle. En dessous du seuil, le verdict est
explicitement « **pas mesurable** » et non « rejeté » — la mutation n'a pas été
réfutée, elle n'a pas pu être jugée — avec une alarme visible dans `make error`. Tous
les jeux réels franchissent le seuil : c'est un fil de détente, pas une règle du jeu.

**Le juge lui-même était biaisé.** Quand la boucle compare un prompt à son mutant, un
côté vient du cache et l'autre d'une évaluation fraîche. Les deux n'étaient pas
construits de la même façon : l'évaluation fraîche connaissait le déplacement exact de
chaque personne, le cache retombait sur un seul déplacement par personne — or 99 % des
gens en ont plusieurs, de motifs et de distances différents. L'écart se logeait
précisément dans les deux dimensions les plus lourdes après le global. Les deux côtés
suivent désormais le même chemin. Effet de bord bienvenu : le score écrit en base est
enfin **exactement** celui qu'on retrouve en le recalculant.

**Une métrique ne peut pas être pondérée par ce qu'elle juge.** Sur les axes ordonnés
(âge, distance), le poids de chaque mode était la masse que le candidat lui accordait
lui-même. Un prompt améliorait donc sa note en **dégonflant** un mode qu'il plaçait mal,
jusqu'à le faire sortir de sa propre évaluation — sans corriger une seule erreur. Le
poids est désormais celui de la référence, identique pour tout le monde.

**Avant :** un prompt évalué sur 8 personnes, à qui quatre dimensions sur six avaient
été offertes faute de données, était déclaré le meilleur du jeu de criblage ; une
évaluation vide obtenait le score parfait ; un mode oublié pesait la moitié de la note ;
et le juge d'acceptation penchait d'un côté avant même de juger.
**Après :** la non-mesure est la pire note possible, jamais la meilleure ; le mode
oublié est une question de recevabilité et non de points ; le test s'abstient au lieu
d'éliminer ce qu'il n'a pas su mesurer ; et les deux côtés de la comparaison sont
construits à l'identique.

**Ce que ça déplace concrètement.** Recalcul des 334 évaluations du store, loss active
(`emd_jsd`) : le composite bouge de **+0,5 point en médiane** (−1,2 à +2,9 hors cas
dégénérés), la corrélation de rang avant/après est de **0,99**, et le meilleur prompt
reste le même sur les trois jeux (`train`, `screen`, `race`). Le classement n'est donc
pas bouleversé — sauf là où il l'était pour de mauvaises raisons : sous la loss L1, le
champion du jeu de criblage change, l'ancien étant le prompt mesuré sur 8 personnes.
Les évaluations dégénérées passent de `0.00` (parfait) à `310` / `620` selon la loss,
au-dessus de la pire évaluation réelle jamais observée (63,5 / 415,8).

---

## [2026-08-11] Calibration : la supervision détecte enfin le travail qui ne produit rien

Une campagne a tourné **quatre jours sans rien produire** et s'apprêtait à annoncer
une convergence. Ce n'est pas qu'une alarme s'est mal levée : les deux alarmes qui
existaient étaient **incapables de se lever** sur cette panne-là. L'une testait la
fraîcheur du fichier d'avancement — que la boucle bloquée réécrivait des dizaines de
fois par heure : elle mesurait que le programme était vivant, pas qu'il avançait.
L'autre était **désactivée tant qu'une passe tournait**, or une passe dure jusqu'à
sept heures : le garde-fou anti-fausse-alerte avait été taillé, sans le savoir, sur
la panne réelle.

La supervision compte désormais **ce qui a été réellement produit** — nouveaux
prompts et évaluations enregistrés — sur une fenêtre de **6 heures glissantes**. Zéro
production sur 6 heures alors que la campagne n'est pas arrêtée : alarme, même si
tout a l'air de tourner. Six heures laissent passer quatre à six générations
légitimes ; l'ancien seuil de 36 h est précisément celui qui a laissé filer
l'incident.

**Avant :** une passe pouvait brûler sept heures de calcul sans produire un seul
candidat, avec un fichier d'avancement rafraîchi en permanence, un digest quotidien
au ton rassurant et aucune alerte. Quatre jours plus tard, la campagne s'apprêtait à
déclarer une convergence qui n'avait rien comparé.
**Après :** l'alarme part sous 6 heures ; le chien de garde alerte **systématiquement**
dès qu'un diagnostic sort en anomalie (l'état « une passe tourne » ne décide plus que
de l'arrêt éventuel du calcul, plus jamais du silence) ; et une passe qui se termine
en état anormal sort en erreur, ce qui déclenche l'alerte système.

**Le digest quotidien dit d'abord l'essentiel.** Première ligne, toujours :
« **Nouveauté depuis hier : OUI / NON** » — avec le nombre de jours écoulés si NON.
C'est le signal qui aurait tout changé ; l'information était déjà là, noyée dans un ton
neutre. Le score est désormais libellé « plus c'est bas, mieux c'est », et le
rassurant « aucun blocage détecté » devient « aucun des problèmes surveillés détecté —
cela ne garantit pas que tout va bien ».

**Deux capteurs cessent de se taire.** La comptabilité d'usage LLM enregistre
maintenant sa ligne **même à zéro requête** : une passe de sept heures sans le moindre
appel ne laissait aucune trace, donc était indistinguable d'une passe qui n'avait pas
tourné. Le digest signale en clair une clé qui a fait tourner une passe pour moins de
100 requêtes. Et l'absence du fichier d'avancement lève désormais un avertissement, au
lieu de rendre la détection de gel aveugle en silence.

**Enfin, la leçon est mise sous test.** Trois tests verrouillent le dispositif : que
l'alarme se lève avec un fichier d'avancement **frais** (la reproduction exacte de
l'angle mort), qu'elle reste **silencieuse** quand la campagne produit (une alarme qui
hurle toujours vaut une alarme muette), et un test de non-régression qui rejoue l'état
réel du 7 août et exige le code d'erreur.

---

## [2026-08-11] Calibration : une coquille de config ne passe plus, et l'instrument de mesure est gravé dans le registre

Le fichier de configuration d'une campagne **est la spécification du protocole
expérimental**. Il était pourtant possible d'y écrire n'importe quoi : une coquille
(`eval_tmp` au lieu de `eval_temp`) et même une clé entièrement inventée étaient
acceptées **sans un mot**, et la campagne tournait alors sur les valeurs par défaut —
des mesures valides en apparence, sous un régime que personne n'avait voulu. Toute clé
inconnue est désormais refusée au lancement, avec un message qui nomme la clé fautive
et propose le champ le plus proche (« `eval_tmp` — vouliez-vous dire `eval_temp` ? »).
Corollaire assumé : une clé orpheline en configuration bloque le démarrage. L'audit
des sept fichiers livrés en a trouvé exactement une, sans le moindre lecteur dans le
code ; elle a été retirée, et un test vérifie désormais que toutes les configurations
livrées chargent.

**Les bras d'ablation cessent d'être des réglages volatils.** Le ciblage
déterministe, la mutation décomposée et la mémoire de leçons sont des *facteurs
expérimentaux*, mais ils ne vivaient que dans une configuration globale et modifiable :
aucune mutation enregistrée ne disait sous quel bras elle avait été produite. C'était
la vraie raison pour laquelle l'ablation de la campagne en cours était réputée
« non interprétable » — pas une fatalité, une colonne manquante. Chaque mutation porte
maintenant son régime, et l'analyse regroupe par bras au lieu de supposer. Les
mutations déjà en base restent en « régime inconnu » : aucune ne se voit attribuer
après coup un bras qu'elle n'a peut-être pas eu.

**On sait enfin sous quel instrument une campagne a mesuré.** La configuration
résolue est archivée dans le registre, empreintée et horodatée, à chaque changement.
Reprendre une campagne dont l'instrument a changé est refusé, avec le détail des
champs qui ont bougé, sauf à assumer explicitement le changement — qui est alors
archivé lui aussi. Les réglages purement opérationnels (chemins, cadences, quotas,
notifications) ne déclenchent rien : rapatrier la base pour la consulter en local
reste anodin.

**Avant :** une coquille de configuration lançait une campagne entière sur des valeurs
par défaut sans le signaler ; rien ne permettait de savoir sous quel bras d'ablation
une mutation avait été proposée, ni sous quelle configuration une campagne avait
tourné — un fichier édité au douzième jour effaçait toute trace du premier.
**Après :** la campagne refuse de démarrer sur une configuration douteuse et dit quoi
corriger ; chaque mutation est attribuable à son bras expérimental ; le registre
conserve l'historique horodaté des configurations, et la reprise sous un autre
instrument doit être assumée.

---

## [2026-08-11] Calibration génétique : fin du blocage silencieux, une campagne ne peut plus « converger » sans rien engendrer

La campagne génétique tournait sans produire le moindre individu : six générations
d'affilée, chaque tentative de reproduction rejetée en doublon, aucun enfant, et un
compteur de stagnation qui montait quand même. Elle s'apprêtait à s'arrêter en
annonçant une convergence — alors qu'elle n'avait comparé le champion qu'à lui-même,
re-mesuré à l'identique trois fois. Cinq correctifs ferment le piège.

- **Le sélecteur d'opérateurs ne peut plus se verrouiller.** Toute tentative de
  reproduction, réussie ou non, met désormais à jour les statistiques de l'opérateur
  employé. Un opérateur qui ne produit rien était auparavant considéré comme « jamais
  essayé », donc rejoué en boucle, indéfiniment.
- **L'opérateur déterministe sort de la compétition.** Le croisement « greedy » est un
  témoin sans appel de modèle : sur une population figée il rend toujours le même
  enfant. Il reste disponible comme repli quand le rédacteur est indisponible, mais
  n'est plus tenté qu'une fois par génération — le rejouer ne produit rien de neuf.
- **Le filet d'exploration redevient atteignable.** L'immigrant aléatoire (un variant
  frais, garde-fou anti-stagnation) était conditionné au « dernier enfant de la
  génération » : une condition impossible à atteindre quand justement aucun enfant
  n'était produit. Il se déclenche maintenant aussi en dernier recours.
- **Une génération stérile lève une alarme et ne compte plus comme une preuve.**
  Reproduction à zéro enfant → `[ALARME]` immédiate dans les logs, avec le détail des
  rejets et l'opérateur en cause. Et surtout : une génération sans candidat nouveau
  n'incrémente plus le compteur de stagnation, puisqu'aucun challenger n'a été opposé
  au champion.
- **Le diagnostic (`calibrate doctor`) teste la stérilité en premier.** Une campagne
  arrêtée renvoyait « ✅ arrêtée » sans autre examen. Deux générations sans le moindre
  candidat nouveau ni éval payée donnent maintenant 🚨 `sterile`, ou 🚨
  `false_convergence` si l'arrêt a été prononcé pour stagnation.

**Cause d'entrée corrigée au passage** : le rédacteur de mutations pointait sur un
fournisseur **qui n'existe pas** dans le catalogue. Rien ne le signalait — la clé d'API
était devinée par convention et les appels partaient quand même — si bien que chaque
mutation échouait et que l'algorithme basculait en permanence sur son repli sans
modèle. Désormais, un fournisseur inconnu est **refusé au démarrage** avec la liste de
ceux qui existent, et une panne **permanente** de configuration (fournisseur ou modèle
inconnu, clé refusée) arrête la campagne au lieu d'être confondue avec un simple quota
épuisé. Le changement de fournisseur est gratuit : le modèle de mutation n'entre pas
dans la clé de cache des évaluations, aucune mesure n'est invalidée.

**Avant :** six générations sans un seul individu engendré, aucun message d'erreur, et
une « convergence » sur le point d'être déclarée à partir de trois mesures du même
prompt ; un fournisseur inexistant faisait tourner la campagne en mode dégradé pendant
quatre jours sans le dire.
**Après :** l'alarme part à la première génération stérile, la stagnation ne se compte
que face à un vrai challenger, le diagnostic quotidien classe le cas en alarme, et une
configuration fautive échoue à la seconde zéro avec un message qui dit quoi corriger.

---

## [2026-08-11] Calibration : loss unique, sélection du champion sur validation, IC sur le chiffre publiable

Trois corrections de **rigueur scientifique** issues du diagnostic multi-angles du module
de calibration (branche `feat/diag-plan-arbitre`), toutes **sans aucun appel LLM** (recalcul
depuis les décisions déjà stockées, aucune invalidation de cache) :

- **Une seule loss de bout en bout.** La pénalité de longueur (poids `1.0`) est mise à `0.0` :
  elle est encore *mesurée* (suivi du nombre de mots) mais n'entre plus dans le composite. Le
  prompt publié est désormais **l'argmin exact de la métrique rapportée** — avant, le champion
  était choisi sous une pénalité que le chiffre publiable neutralisait. L'économie de mots reste
  assurée par la passe de compaction.
- **Champion sélectionné sur la validation, pas l'entraînement.** `finalize` prend le meilleur
  composite sur `val` (repli sur `train` si absent), supprimant le biais de surapprentissage au
  jeu que la boucle optimise.
- **Intervalle de confiance sur le résultat.** `calibrate finalize` affiche désormais un IC à
  90 % (bootstrap apparié) sur l'amélioration test seed→champion, au lieu d'un simple point.

**Modèle d'évaluation figé** pour la campagne de référence : nouvelle entrée provider
`google_gemini31_ga` sur `gemini-3.1-flash-lite` (version GA datée `05-2026`) au lieu de la
preview flottante, qui pouvait changer sous nos pieds sans que rien ne le signale. La campagne
en cours n'est pas touchée : le provider entrant dans la clé de cache, la version figée dispose
de son propre cache et de son propre quota journalier.

Ajout de garde-fous de fiabilité : un échec persistant du mutateur **arrête proprement** la
campagne (`[ALARME]`) au lieu de la déclarer « terminée » à vide ; une campagne finissant sans
aucune acceptation est signalée en **échec** ; le jeu de test est **verrouillé au démarrage**
(disjonction vérifiée, fail-fast) ; un garde **refuse un modèle d'éval non épinglé sur un run
neuf** (sans jamais bloquer la reprise d'une campagne en cours).

**Avant :** prompt publié ≠ argmin de la métrique rapportée ; champion choisi sur `train` ;
résultat test = un point sans dispersion ; un mutateur en panne pouvait produire une « campagne
terminée » sans rien avoir calibré.
**Après :** sélection = reporting ; champion choisi sur `val` ; résultat test = Δ + IC90 ;
échec vacant détecté et signalé.

---

## [2026-08-04] Calibration : rapports HTML livrés sur Discord et suivi d'avancement lisible

Les rapports de génération (`gen_NN.html`) et le bilan hebdomadaire arrivent
désormais **en pièce jointe du message Discord** — un clic pour les télécharger,
plus besoin de configurer un compte mail (le canal SMTP reste disponible en
option). Le message d'avancement est réécrit pour se lire d'un coup d'œil.

**Avant :** rapport joint uniquement au mail (inactif sans secrets SMTP) ;
message : `attribution par omission (génération 0, jeu rank) · 5/7 (71 %) · ·
5/7 ga ablation g0[6b:7b407ee7] lot 3/27` + `Itération 0/50 · 0 itér ·
0 acceptée(s)` + `Appels LLM 252`
**Après :** rapport téléchargeable dans Discord ; message : `attribution par
omission (génération 0 · prompt candidat 2/3, jeu rank) · 5/7 (71 %) ·
lot 3/27` + `Évals : 6 payée(s) (appels LLM) · 1 par le cache (0 appel)` +
`Appels LLM : 252 / 500 (quota du jour de la clé)` + `Reste (étape) :
~2 coalition(s) ≤ 90 appels` — les compteurs d'itération n'apparaissent que
quand une boucle a réellement itéré.

Même passe de lisibilité sur les deux autres familles de messages : le **digest
quotidien** n'affiche plus `Itération : None` sur une campagne génétique et
nomme l'étape GA en clair (`Étape GA : attribution par omission`) ; le
**rapport de génération** dit « Champion : prompt candidat a1c20fb104 » et
explique le budget (« évals accumulées, réutilisables gratuitement »).

---

## [2026-08-03] Calibration : le rattrapage des lots incomplets ne re-paye plus les personas déjà rendus

Le modèle d'éval de la campagne génétique (`gemini-3.5-flash-lite`) omet ~10 % des
personas de chaque lot. Le rattrapage re-tirait alors **deux moitiés complètes** du
lot : un lot de 8 avec 6 rendus re-payait 8 personas en 2 appels pour 2 manquants.
Sur la journée du 2026-08-03 (250 re-tirs), environ **la moitié du quota journalier
bi-clé** (~1 000 requêtes) est partie en rattrapage au lieu de payer des évals.

Le re-tir est désormais **ciblé** : un seul appel ne contenant que les personas
manquants. Le découpage en moitiés ne subsiste que pour un lot rendu entièrement
muet (le redemander à l'identique à température 0 redonnerait la même réponse).
La mesure est inchangée (le re-tir n'entre pas dans la clé de cache d'éval).

**Avant :** lot de 8 avec 2 manquants → 2 appels re-payant 8 personas (et récursion)
**Après :** lot de 8 avec 2 manquants → 1 appel de 2 personas

---

## [2026-08-03] Drainage nocturne des réflexions STM : la vague du soir n'est plus une fausse alerte

Les agents rentrent le soir avec leurs mémoires pleines et déclenchent tous leur
réflexion STM dans la même fenêtre (run de référence : 247 réflexions pour
13 décisions d'itinéraire en 30 min simulées). Ce stock est désormais traité pour
ce qu'il est — une charge incompressible mais **sans urgence**, à servir pendant la
nuit simulée où la capacité LLM est libre — et non comme une saturation du pipeline.

- **Échéance au réveil** : chaque réflexion part en file EDF avec pour échéance le
  réveil de son agent (première activité du lendemain), au lieu d'un délai fixe de
  12 h. Les décisions du soir passent mécaniquement devant ; le stock se draine
  toute la nuit dans l'ordre des réveils (lève-tôt d'abord). Aucune réflexion n'est
  abandonnée ni tronquée : on déplace la charge dans le temps, on ne la réduit pas.
- **Alarme backlog honnête** : `[ALARME] Backlog critique` ne crie plus que si des
  décisions d'itinéraire souffrent réellement (départs en retard ou échéances
  dépassées). Une pile dominée par les réflexions la nuit est loggée en INFO avec sa
  composition (`N décisions + M réflexions`).
- **Drainage post-pause visible** : à la fin d'horizon (`simulation_max_days`), le
  controller continue d'écrire les réflexions restantes en LTM et le signale dans
  les logs (`[drainage] … arrêt sûr (make down)` quand la file est vide).
- **Cockpit** : nouveau panneau Grafana « Composition de la file LLM »
  (`itinary_multi_agent` vs `stm_reflection`, décisions à échéance dépassée) — la
  donnée qui a permis le diagnostic, lisible d'un coup d'œil.

**Before :** la vague de réflexions du soir déclenchait `[ALARME] Backlog critique`
et masquait la composition de la file (80 % de backlog alors que late=0, cache 99 %,
providers sains)
**After :** nuit simulée = drainage nominal tracé en INFO ; l'ERROR ne part que si
des décisions d'itinéraire sont réellement en souffrance, et chaque réflexion est
terminée avant le réveil de son agent

---

## [2026-08-03] Calibration : plus de crash sur une réponse persona vide, alertes Discord qui nomment la bonne unité

La passe génétique du matin (`calib-ga-pm`, clé Google 2) s'est arrêtée net : le
modèle d'éval a rendu, pour un persona, une entrée **vide** (ni distribution de
probabilités, ni mode). L'entrée passait pour « rendue » (pas de re-tir), et la
décision `mode=None` fabriquée en aval faisait exploser la validation d'`EvalResult`
après avoir payé tous les lots de l'éval. Une telle entrée est désormais traitée
comme un **persona non rendu** : re-tir par moitiés, puis garde de couverture s'il
reste muet — mêmes défenses que le lot incomplet, aucune mesure dégradée. La passe
interrompue a été relancée et a repris exactement à l'étape du crash (cache intact).

Au passage, l'alerte Discord `OnFailure` annonçait « le service calib » en dur,
quelle que soit l'unité morte — le diagnostic est parti sur la mauvaise unité.
`calib-notify-fail` est maintenant une unité template : le message nomme l'unité
réellement en échec et la bonne commande `journalctl`.

**Before :** une réponse persona vide tuait toute la passe GA après avoir consommé
le quota de l'éval ; l'alerte Discord pointait `journalctl -u calib` même quand
c'était `calib-ga-pm` qui était mort
**After :** le persona vide est re-tiré puis compté par la garde de couverture ;
l'alerte nomme l'unité en échec et la commande de diagnostic exacte

---

## [2026-08-03] Dashboard : la campagne génétique en détail (population, scores, rapports)

La section **Campagne génétique** de l'onglet 🧬 Calibration montre désormais ce
qui se passe réellement sur la VM : génération et étape courante du cycle GA
(8 étapes, de `populate` à `breed`), et surtout **la population individu par
individu** — profil (élite reprise du recuit, axes semés « identification »,
« météo », « minimaliste »…), opérateur d'origine, génération d'apparition, date
de création, et les trois scores avec leur rôle : `rank` (le score de sélection,
celui de la coupe), `screen` (confirmation du champion), `val` (early stopping).
La progression intra-étape est visible (« population évaluée 1/10 »), ainsi que
l'activité récente (dernière éval, évals sur 24 h) et l'historique
`champion_par_génération`.

Les rapports HTML par génération, générés sur la VM et jamais rapatriés
jusqu'ici, se récupèrent d'un bouton (`make pull-reports`, nouvelle cible) et
s'ouvrent depuis la page. Un mémo intégré explique comment activer les rapports
par mail (adresse dans `config/ga_cloud.yaml`, secrets SMTP dans `~/calib.env`
sur la VM).

**Before :** l'état de la campagne GA se devinait via `make cloud-logs` ; les
scores de la population et les rapports par génération restaient sur la VM
**After :** population, scores et progression lisibles dans l'onglet, rapports
rapatriables et consultables en un clic

---

## [2026-08-03] Dashboard : onglet Calibration avec supervision de la VM cloud, commandes contextuelles

Le dashboard gagne un onglet **🧬 Calibration** : stores local/cloud (scores,
branches), état de la **campagne génétique** (génération, étape, champion — lu
dans la branche `__ga__` du store), veille quota, vivacité du daemon local
(`progress.json`), et supervision de la VM `calib-vm` : `cloud-progress`,
`cloud-status` et `cloud-logs` s'exécutent sur bouton avec la sortie affichée
dans la page (chaque clic = un SSH, rien d'automatique), `pull-db` / `pause` /
`start` en actions. Le sélecteur de campagne vise `config/ga_cloud.yaml`
(ticket 009) par défaut et `cloud-logs` accepte désormais `UNIT=calib-ga`.

Les commandes sont par ailleurs intégrées au plus près des métriques de chaque
domaine : services Docker → `up`/`restart`/`down`, synthèse → `synthesis`/
`synthesis-open`, en plus des actions déjà présentes dans Run GAMA et Providers.
Le volet ▶ Commandes reste le catalogue complet.

**Before :** la calibration ne montrait que les stores locaux ; l'état de la VM
exigeait un terminal (`make cloud-progress`…), et `cloud-logs` restait câblé sur
l'ancien daemon `calib`
**After :** tout le pilotage calibration (y compris cloud/GA) dans un onglet,
avec la sortie SSH rendue dans la page

Côté `prompt_calibration` : nouvelle cible `make pull-db` (rapatrie le store
sans ouvrir de dashboard, scriptable) et variable `UNIT` pour `cloud-logs`.

---

## [2026-08-03] Dashboard : vue d'ensemble, pilotage du run GAMA et des providers

Le dashboard de pilotage (`make dashboard`) gagne trois volets qui répondent en
un coup d'œil à « où en est le projet ? » et pilotent le run sans terminal :

- **🏠 Vue d'ensemble** — six feux rafraîchis toutes les 10 s : services Docker,
  run GAMA, providers LLM, calibration (avec la fraîcheur du store cloud
  rapatrié), git et jobs en cours.
- **🎮 Run GAMA** — état du run en direct (heartbeat, cycle, agents actifs,
  backlog), courbe de progression inactifs/prêts/actifs, top des messages
  d'erreur du log, hit rate du cache LLM et 429 ; boutons pour lancer un run
  offline (choix du `CONFIG`, confirmation), l'arrêter proprement et générer le
  rapport `make report` directement dans la page.
- **🤖 Providers** — quotas et disponibilité temps réel vus par le load balancer
  (RPM, requêtes/tokens du jour face aux RPD/TPD, cooldowns), avec repli sur
  `providers.yaml` quand la pile est arrêtée ; boutons `make providers`
  (bilan à blanc puis rafraîchissement réel).

Deux nouvelles cibles make accompagnent le volet Run : `make status` (le run
est-il actif ? sortie parsable) et `make stop-run` (arrête le launcher headless
et le service `gama` sans couper le reste de la pile).

**Before :** l'état du run, des providers et des caches se reconstituait au
terminal (`make error`, `curl :8000/health`, `pgrep`…) ; aucun arrêt de run
autre que `make down`
**After :** un onglet par préoccupation, rafraîchi automatiquement, avec les
actions à portée de bouton

---

## [2026-08-03] Les re-runs ne repayent plus les réflexions : mémoïsation exacte

Les appels LLM de réflexion (STM et auto-réflexion LTM) sont désormais mémoïsés
par empreinte exacte du prompt effectif (`ReflectionMemoStore`,
`reflections.sqlite` à côté du cache de décisions). Sur un **re-run déterministe**
(décisions au cache, tirages seedés, météo rejouée), le vécu des agents est
byte-identique : chaque réflexion déjà payée est servie sans appel réseau, avec
des effets identiques (STM consommée, LTM écrite). Les réflexions étaient le
premier poste de quota d'une relance de run de référence (95 % des tâches LLM du
pic du soir sur la campagne du 2026-08-03).

**Before :** relancer le run de référence repayait toutes les réflexions
**After :** re-run du même scénario → hits `[reflection-memo]`, zéro quota réflexion

Garde-fous : correspondance exacte uniquement (jamais entre agents ni entre vécus
différents — l'introspection d'un agent ne sert jamais à un autre), réflexions
vides jamais persistées, invalidation automatique au changement de prompt système
(répertoire par checksum). Désactivable via `cache.reflection_memo_enabled`.
Compteurs Prometheus `agent_reflection_memo_total` (hit/miss/store). Sur un
scénario inédit, comportement inchangé (~0 % de hit). La mesure de validation
(re-run du scénario épinglé, hit attendu ≈ 100 %) reste à produire — ticket 012, A3.

---

## [2026-08-03] Le cache LLM n'apprend plus le hasard : replis uniformes non persistés

Quand un provider renvoie un vecteur de probabilités inexploitable (troncature,
somme nulle), le repli uniforme permet toujours au trajet en cours d'être tiré au
sort — mais cette distribution n'est **plus écrite dans le cache persistant**.
Avant, elle y entrait comme une décision légitime : tout run ultérieur touchant la
clé tirait son mode à parts égales, en croyant servir le modèle (« le cache n'a
aucun mode dégradé » était violé silencieusement).

**Before :** repli uniforme → cache → les runs suivants héritent du hasard
**After :** repli uniforme → trajet courant seulement, log `[cache] store refusé`,
le prochain passage sur la clé redemande au LLM

Découvert pendant la campagne NO_GOOGLE du 2026-08-03 : `cerebras_zai-glm-4.7`
tronquait ~100 % de ses réponses (`finish_reason=length`) et a déposé 7 replis en
cache. Le provider est **retiré de la cascade** (commenté dans providers.yaml avec
les conditions de réactivation) et `scripts/cache/purge_uniform_fallback.py`
retire les points uniformes du cache (dry-run par défaut, controller arrêté).

---

## [2026-08-03] NO_GOOGLE=1 : run sans les modèles Google

`make run NO_GOOGLE=1` lance une campagne en excluant tous les modèles Google
(gemini, gemma — clés 1 et 2) de la rotation LLM. Le mécanisme existant fait le
travail : les clés sont blanchies dans les conteneurs et
`filter_providers_without_api_key` retire les instances `google*` de la cascade,
qui continue sur mistral/groq/cerebras. Combinable avec le mode headless :
`make run OFFLINE=1 NO_GOOGLE=1`.

Usage type : préserver les 500 requêtes/jour par modèle des clés Google pour les
mesures (`common-set-eval`, `heldout-eval`) pendant qu'une campagne tourne.

**Before :** exclure Google demandait de manipuler les variables `PROVIDER_KEYS__*`
à la main (et la clé 2 restait injectée via `.env` quoi qu'il arrive)
**After :** `make run NO_GOOGLE=1` — l'exclusion est visible au démarrage dans les
logs (`Fournisseur 'google…' exclu : clé API manquante`)

---

## [2026-08-03] Mode offline : GAMA headless en conteneur, run 100 % Docker

`make run OFFLINE=1` (alias `make run-offline`) lance désormais la simulation
sans IHM GAMA : le service compose `gama` (image officielle
`gamaplatform/gama:2025.06.4`, profil `offline`) démarre en mode GAMA Server et
le launcher `scripts/gama/launch_headless.py` pilote `load` + `play` via le
protocole WebSocket (port 6868). Le run devient entièrement scriptable — runs de
nuit, relances automatiques de run de référence et lancements depuis la VM de
calibration deviennent possibles sans poste avec GAMA installé.

**Before :** `docker compose up`, puis ouvrir GAMA sur l'hôte et cliquer Play
**After :** `make run OFFLINE=1` — tout démarre en conteneurs, console GAMA
relayée dans `experiments/current/gama_headless.log`

Le mode IHM reste inchangé (`make run` sans variable) : les défauts
`localhost`/`host.docker.internal` sont conservés, le mode offline les surcharge
via les nouveaux paramètres `http_url`/`http_port` de l'expériment `e` et la
variable d'environnement `GAMA_WS_URL`.

---

## [2026-08-03] make providers : quotas réels auto-relevés, cycle de vie des modèles, garde-fou Mistral

Nouvelle commande `make providers` (option `DRY_RUN=1`) : elle relève les quotas
free tier **réels** de chaque provider et met à jour `providers.yaml` en préservant
les commentaires. Sources : en-têtes `x-ratelimit-*` (Mistral/Groq/Cerebras, une
requête sonde d'un token par instance) et API Cloud Quotas Google (la doc publique
ne liste plus les quotas par modèle). Une sonde en échec laisse l'instance intacte
et lève une `[ALARME]`.

La commande gère aussi le **cycle de vie des modèles** : un nouveau modèle texte
opérationnel est ajouté automatiquement avec ses quotas relevés — **en rotation**
si son RPD free tier ≥ 100, sinon **hors rotation** (`weight: 0`, nouveau
mécanisme : le load balancer exclut les weight 0 de la séquence SWRR, le provider
restant utilisable en `llm.provider` forcé). Un `default_model` disparu de l'offre
est **commenté avec la date** et signalé par `[ALARME]`. Garde-fous : jamais de
ré-ajout d'un modèle déjà référencé (même commenté = décision humaine), pas
d'ajout Google sur une famille de quota déjà exploitée (le stable et le -preview
partagent le même seau), pas d'ajout Mistral (quota partagé par compte, aucun gain).

Premier passage appliqué : les requêtes/jour manquaient au fichier (Groq 1 000/j
sur llama-3.3 et gpt-oss-120b !, Cerebras 2 400/j) — le limiteur journalier les
applique désormais au lieu de découvrir les 429 en cours de run. Les poids SWRR
sont recalés sur la convention `min(rpm, tpm/3000)/15`. Deux nouveaux seaux
rejoignent la rotation : `cerebras_gemma_4_31b` (2 400 req/j, indépendant du
quota Google des Gemma) et `groq_qwen_qwen3_6_27b` (1 000 req/j) ; trois modèles
Gemini récents (3-flash-preview, 3.5-flash, 3.6-flash — 20 req/j chacun) sont
définis hors rotation pour les essais ciblés.

**Garde-fou Mistral** : le free tier est plafonné à 1 Md de tokens/mois (invisible
côté API). Pour qu'un run ne consomme pas le mois en une journée, `tpd_limit` est
forcé à 3× le prorata journalier (100 M tokens/jour). Le RPM est aligné sur la
cadence documentée (60, soit 1 req/s) au lieu du 90 historique.

**Avant :** quotas et offre de modèles relevés à la main sur les dashboards, RPD absents, TPD Mistral « TBC »
**Après :** `make providers` recale quotas et poids, active les nouveaux seaux, commente (daté) les modèles disparus — bilan en console en ~30 s

---

## [2026-08-03] Calibration génétique : éval bi-clé matinale sur Gemini 3.5 Flash Lite

L'évaluation de la campagne génétique passe de `gemini-3.1-flash-lite-preview` à
`gemini-3.5-flash-lite` (décision prise à J+1, ~2 évals en cache : seul moment où le
changement de régime était gratuit) et se consomme désormais sur **les deux clés
Google** : deux passes one-shot par jour, tirées au sort dans la matinée (clé 1 entre
09h et 11h, clé 2 entre 11h et 13h, Europe/Paris). Le provider d'éval reste unique
(la clé est injectée au lancement) → un seul régime de mesure, cache d'éval partagé.
Le daemon continu est remplacé par ces deux timers.

**Avant :** 500 appels/jour, campagne au fil de l'eau, ~1 génération tous les 2 jours
**Après :** ~1 000 appels/jour concentrés le matin, ~1 génération par jour

Nouveaux contrôles : `calibrate ga --clear-cooldown` (bascule de clé) et
`--override-stall` (reprendre une campagne arrêtée sur stagnation si le champion ne
convainc pas — la finalisation reste une commande manuelle, en dry-run par défaut).

---

## [2026-08-02] Calibration génétique : une population de prompts évolue seule sur le cloud

La calibration du prompt `itinary_multi_agent` dispose d'un second orchestrateur
(ticket 009) : un algorithme génétique (μ+λ) élitiste — 10 prompts en concurrence,
coupe aux 5 meilleurs, 5 enfants par génération via 4 opérateurs (croisement informé
par l'ablation, croisement greedy sans LLM, mutation ciblée, exploration par levier
comportemental) mis en concurrence par le bandit UCB1. Il explore l'espace des
structures de prompt là où le recuit raffine une trajectoire ; les deux partagent le
même store et le jeu `test` reste scellé jusqu'à la finalisation.

La campagne tourne en autonomie sur la VM cloud (`calibrate ga --loop`, service
`calib-ga`) : elle consomme le quota du jour, dort jusqu'au reset, reprend seule.
À chaque génération : rapport HTML autonome (trajectoire du champion, prompt annoté
phrase par phrase, parts modales vs EMC²), compte rendu Discord et **e-mail avec le
rapport joint**. Un **bilan hebdomadaire** (Discord + mail) part chaque lundi matin ;
le digest quotidien Discord continue de couvrir les jours creux.

**Avant :** une seule trajectoire de recuit, comptes rendus Discord uniquement.
**Après :** population explorée en parallèle, sélection étanche (rank ⊂ screen ⊂ train),
rapport de génération auto-portant envoyé par mail, bilan hebdo automatique.

---

## [2026-08-03] Pénurie de tokens ou coupure LLM de 24h : la simulation attend le renouvellement, sans dégrader aucune décision

Face à une panne durable du gateway LLM (quotas journaliers de tous les providers
épuisés, service ou réseau coupé), la simulation **se met en pause proprement et attend
le rétablissement** — elle ne prend plus des heures de décisions dégradées.

**Disjoncteur client.** Après 10 échecs consécutifs — y compris les coupures réseau
franches, qui échappaient auparavant à toute alarme —, les soumissions LLM sont
suspendues : aucune tâche ne part plus brûler son timeout (jusqu'à 120 s chacune),
aucune décision n'est prise hors du chemin nominal (cache exact ou appel LLM). La
contre-pression `/sync` existante retient GAMA : le temps simulé n'avance plus tant que
les décisions ne reviennent pas. Une sonde re-teste le gateway toutes les 60 s ; au
premier succès (renouvellement des quotas à minuit UTC, retour du service), toutes les
soumissions suspendues repartent avec de vraies décisions LLM — reprise automatique,
sans redémarrage ni intervention.

**Avant :** une rupture de 24 h = des milliers de décisions dégradées en « premier
itinéraire de la liste » (biais modal non maîtrisé dans `moves.csv`), chacune après
48–120 s d'attente ; et une coupure réseau franche ne déclenchait même pas l'alarme
gateway.
**Après :** la simulation attend tranquillement, `moves.csv` ne contient que des
décisions nominales, la panne est visible au cockpit (`[ALARME]`, gauges
`llm_gateway_circuit_open` / `llm_gateway_circuit_waiters`), et tout repart seul à la
première sonde réussie.

Réglages : `agent.remote_llm_circuit_failure_threshold` (0 = désactivé, comportement
historique) et `agent.remote_llm_circuit_probe_interval`.

---

## [2026-08-02] Un tableau de bord pour piloter le dépôt

`make dashboard` ouvre une page qui rassemble les trois choses qu'on allait chercher
ailleurs : les commandes, les tickets et les chiffres.

**Les commandes.** Les cibles `make` de la racine, de `prompt_calibration` et
d'`otp-toulouse` sont listées avec leur documentation — celle des commentaires `##` du
Makefile —, groupées par thème et lançables d'un bouton. Les variables utiles
(`CONFIG`, `RUN`, `ESSAI`, `DRY_RUN`…) se saisissent dans un tiroir, qui affiche aussi la
ligne de commande équivalente. Chaque cible porte ce qu'il faut savoir avant de cliquer :
elle ne rend pas la main ⏳, elle consomme du quota LLM 💸, elle détruit des données 🔥
(case de confirmation obligatoire), elle pose une question au clavier ⌨️ (bouton
désactivé, à lancer en terminal). La sortie défile en direct, le bouton « Stop » tue le
groupe de processus — y compris les `docker compose` enfants — et chaque lancement laisse
son log complet dans `experiments/.dashboard/`.

**Les tickets.** Les huit tickets de `docs/tickets/` sont tableautés avec un statut déduit
de leurs cases à cocher et de leur ligne `**État**`, une barre d'avancement et la date de
dernière modification. La déduction se surcharge à la main dans
`scripts/dashboard/tickets_status.yaml`.

**Les chiffres.** Conteneurs Docker actifs ; erreurs, warnings et `[ALARME]` du run choisi ;
trajets, agents, heures simulées, part décidée par le LLM et partage modal lus dans son
`moves.csv` ; écarts au référentiel Cerema de la page de synthèse ; avancement des campagnes
de calibration locale et cloud, branche par branche.

**Avant :** trois terminaux, un `ls experiments/archive`, un `grep ERROR`, un `sqlite3` sur
le store de calibration et une lecture de chaque ticket pour savoir où on en était.
**Après :** `make dashboard`, une page.

La liste des runs dédoublonne le lien `experiments/current` et l'archive vers laquelle il
pointe : le run courant y figure une seule fois, en tête, marqué « (en cours) ».

---

## [2026-08-02] Plus d'erreur « metadata value too long » à l'ouverture des modèles

L'éditeur GAMA refusait d'enregistrer les métadonnées de `Inhabitant.gaml` et affichait une
erreur au démarrage. En cause : les accents dans la ligne `Tags:` de l'en-tête des modèles.
GAMA sérialise ces tags dans une propriété persistante Eclipse, et à chaque aller-retour
lecture/écriture un « é » se ré-encodait sur lui-même (`é` → `Ã©` → `ÃÂ©`…), doublant de
taille à chaque session jusqu'à dépasser la limite de 2 Ko d'Eclipse.

Les tags des modèles sont désormais en ASCII pur (`mobilite`, `reseau`). Le reste des
en-têtes et des commentaires garde ses accents — seule la ligne `Tags:` est concernée.

**Avant :** `Could not set property: gama.ui.application metadata. Value is too long.` à
chaque ouverture, métadonnées du modèle jamais mises à jour
**Après :** métadonnées enregistrées normalement, plus d'erreur

---

## [2026-08-02] La page de synthèse décrit un run de 24 h, et les trois volets s'y accordent

Nouveau run épinglé : 24 heures simulées sur la population corrigée, cache LLM débrayé
pour que chaque décision laisse une trace. Les trois volets portent enfin le **même**
périmètre — même run, même jour, mêmes exclusions — et la page l'affiche au lieu de le
laisser supposer.

| | Décisions | Personnes |
|---|---:|---:|
| Volets 1 et 3 | 2 830 | 867 |
| Volet 2 | 181 | 75 |

**Avant :** 6 510 lignes lues sur 5 jours, replis d'erreur compris, et un volet 2 mesuré
sur un autre run.
**Après :** 1 656 lignes écartées par le filtre de jour, 400 par les méthodes sans
décision, un jour unique (16 mars) annoncé par les trois volets.

Ce que le run change, mesuré plutôt qu'espéré :

- **plus aucun mineur ni sans-permis au volant** — 0 trajet contre 480 auparavant, dont
  310 conduits par des moins de 14 ans. Les enfants se déplacent toujours en voiture
  (69,6 % de leurs trajets), mais en passager : 608 trajets, marqués comme tels ;
- **la marche revient sur les retours courts** — sur les retours au domicile de moins d'un
  kilomètre décidés automatiquement, elle passe de 7,6 % à 42,9 %. Et ces décisions
  automatiques s'effondrent de 158 à 14 : le verrou ne réduit plus le jeu de choix à un
  seul mode, l'agent choisit vraiment ;
- **0 scolaire en déplacement « Travail »**, contre 214.

Deux alarmes sont **attendues et assumées**, pas masquées. Les véhicules orphelins passent
à 5,1 % des retours (39 sur 767) et déclenchent l'alarme : c'est l'effet mécanique du seuil
d'un kilomètre, et le seuil d'alarme n'a pas été relevé pour la faire taire. Les 39 alarmes
de saturation LLM viennent du cache débrayé — toutes les décisions partent au modèle — et
portent les replis d'erreur à 14,1 % du journal ; ils sont exclus du scoring, ce pour quoi
cette exclusion existe.

La lignée de prompts est re-mesurée sur les jeux `v2` : composite 23,36 pour la graine,
24,04 pour le meilleur prompt sur le jeu de retenue. La page **prévient explicitement** que
le score d'entraînement vient de `v1` (météo uniformément ensoleillée) et celui de retenue
de `v2` (météo tirée dans l'année) : l'écart entre les deux ne mesure pas que la
généralisation, et le témoin d'effectif ne neutralise pas cette part-là.

---

## [2026-08-02] Un run mesurable de bout en bout : cache LLM débrayable, clé Google dédiée

Le premier run de 24 h a révélé un angle mort. Une décision servie par le **cache
sémantique** ne laisse aucune trace dans `llm_exchanges.jsonl` — seulement une ligne dans
`llm_cache_hits.jsonl`. Or ce journal est la seule source du volet 2 de la page de
synthèse. Sur ce run, 2 325 décisions sont venues du cache : les volets 1 et 3 en
portaient 3 084, le volet 2 en portait **23**, avec 27 strates sous le seuil d'effectif.
Les trois volets ne mesuraient plus le même run — exactement ce que le contrôle de
périmètre était censé empêcher, mais par un chemin qu'il ne couvrait pas.

**Avant :** un run bien caché est un run bon marché… et un volet 2 vide, sans que rien ne
l'annonce.
**Après :** `make run CONFIG=config_baseline_1000_nocache.yaml` produit un run où chaque
décision passe par un appel LLM réel, donc atterrit dans le journal. Le cache reste le
défaut en production — il n'est débrayé que pour produire un run de référence.

Dans la foulée, la simulation tourne désormais sur la **seconde clé Google**. Les quotas
free tier Gemini se comptent par projet et par modèle : la simulation consomme ceux de la
clé 2, pendant que les ré-évaluations de la page gardent les 500 requêtes/jour de la clé 1.
La cascade multi-providers est intacte — mistral, groq et cerebras n'ont pas bougé.

Enfin, un piège de plus a été fermé au passage : le store de calibration indexe une
évaluation sur le nom du jeu, sans sa version. « test » désignant deux jeux différents en
v1 et en v2, une mesure v1 aurait été resservie pour une demande v2 — zéro appel, et un
chiffre étiqueté du mauvais régime météo. Le nom porte maintenant la version.

---

## [2026-08-02] Il pleut enfin dans les jeux de calibration

Les jeux gelés qui servent à noter le prompt ne contenaient que **cinq valeurs météo,
toutes ensoleillées** : le run source couvrait trois jours de mars 2026, et ces trois jours
étaient secs. Le prompt était donc calibré dans un monde où il ne pleut jamais — alors que
la météo est précisément l'un des leviers qu'on lui demande de peser.

La source, elle, n'avait rien d'appauvri : l'année climatique de Toulouse compte 365 jours
dont 155 avec précipitations. Une nouvelle version des jeux (`v2`) **tire la météo dans
cette année complète**, au créneau horaire du départ du persona, avec une graine
reproductible consignée dans le manifeste. Deux régénérations produisent des fichiers
identiques à l'octet.

**Avant :** 5 conditions météo, 5 températures, 0 % de jours pluvieux dans le train.
**Après :** 16 conditions, 45 températures, 43,7 % de records avec précipitations — la
distribution de l'année.

La contrepartie est assumée : un score mesuré sur `v2` ne se compare pas à un score `v1`.
La lignée retenue est donc re-mesurée sur `v2`, et le régime météo doit apparaître dans la
page de synthèse — sans quoi un lecteur comparerait des chiffres qui ne mesurent pas la
même chose.

Un garde-fou accompagne le changement : le gel d'un jeu est **refusé** si un seul record a
un contexte météo vide. Le format des échanges ayant changé (la météo se trouve maintenant
dans chaque bloc persona, plus dans un préambule commun), une lecture naïve produisait des
contextes vides sur la totalité des records — les blocs seraient partis sans météo, en
silence, et personne ne l'aurait vu avant d'avoir payé une campagne entière.

---

## [2026-08-02] La page de synthèse dit enfin sur quoi elle porte

Les trois volets de la page pouvaient mesurer trois sous-ensembles différents du même run
sans que rien ne le signale. Deux coupes, désormais définies une fois et appliquées aux
trois :

- **Les replis d'erreur LLM sortent du scoring.** Quand le prompt ne répond pas, le
  contrôleur prend l'itinéraire par défaut : sur le run de référence, 100 % de ces 431
  lignes retenaient le plus rapide, soit 64,7 % de voiture. Les compter revenait à noter le
  prompt sur un choix qu'il n'a pas fait.
- **Un seul jour simulé**, le premier du run. Le bootstrap 24 h et l'horizon glissant de
  planification font déborder le journal au-delà : 2 538 couples (personne, activité)
  réapparaissaient un jour plus tard, avec le même mode dans 57,8 % des cas. Ce ne sont pas
  des décisions supplémentaires, elles pèsent seulement deux fois dans les parts modales.

**Avant :** 6 510 lignes lues, sur 5 jours, replis d'erreur compris — et le volet 2, qui
lit un autre fichier, n'appliquait aucune de ces règles.
**Après :** un périmètre unique, annoncé dans le bilan de lecture (jour retenu, lignes
écartées par méthode, lignes écartées par jour), et vérifiable en comparant les effectifs
des trois volets.

La page ventile aussi la nouvelle colonne « Contrainte de chaîne » : elle dit quelle part
des décisions a été prise sur un jeu d'options déjà restreint par la cohérence des
véhicules. Ces lignes restent dans le score — c'est bien ce que la simulation a joué — mais
le lecteur sait maintenant de combien il s'agit.

---

## [2026-08-02] Un run de 24 h s'arrête au bout de 24 h

Le paramètre « nombre maximal de jours simulés » existait, s'affichait dans l'IHM… et
n'arrêtait rien : l'instruction d'arrêt du reflex correspondant était commentée. Un run
demandé sur 24 h en produisait trois, et personne ne pouvait le savoir après coup — la
valeur n'était consignée nulle part dans le répertoire d'expérience.

**Avant :** la simulation tournait jusqu'à ce qu'on l'interrompe à la main, et le run
archivé ne disait pas sur quel horizon il était censé porter.
**Après :** elle se met en pause d'elle-même à l'horizon demandé, et
`scenario_params.yaml` le consigne.

C'est une **pause**, pas une mort : l'horloge s'arrête, les agents et les sorties restent
inspectables, et le contrôleur Python n'est pas interrompu — ses écritures en cours se
terminent normalement. GAMA reste donc ouvert après l'arrêt ; les conteneurs se coupent à
la main une fois le journal complet.

L'instruction commentée l'était pour une raison qu'il a fallu redécouvrir : le reflex se
trouvait dans le bloc `experiment`, où l'action n'existe pas — à cet endroit, il n'aurait
jamais pu compiler. Il est désormais déclaré dans `global`, avec les agents dont il arrête
l'horloge.

---

## [2026-08-02] Le journal de déplacements dit pourquoi le choix était contraint

Nouvelle colonne **« Contrainte de chaîne »** dans `moves.csv`, juste après la méthode de
sélection. Elle distingue quatre situations : aucun filtre, retour forcé (l'agent ramène
son véhicule), trajet en passager, ou mode véhiculé écarté faute de véhicule sur place.

**Avant :** un trajet en voiture au retour du bureau et un trajet en voiture librement
choisi étaient indiscernables dans le journal.
**Après :** on lit lequel des deux c'était, et la page de synthèse en publie la
répartition.

La colonne **explique, elle ne filtre pas** : ces lignes restent dans le scoring. Le mode
d'un trajet passager reste « Voiture Privée » — l'enquête EMC² compte le passager dans
« voiture », créer un septième mode casserait la comparaison.

---

## [2026-08-02] On ne reprend plus sa voiture pour rentrer de deux cents mètres

Le verrou de retour — l'agent ramène chez lui le véhicule qu'il a garé quelque part —
s'appliquait à toutes les distances. Sur les retours au domicile de moins d'un kilomètre,
59,5 % se faisaient en voiture et 7,6 % à pied, contre environ 76 % de marche attendus par
l'enquête EMC².

**Avant :** un agent ayant garé sa voiture à 300 m de chez lui n'avait pas d'autre option
que de la reprendre.
**Après :** sous 1 km, tous les modes restent offerts. S'il rentre à pied, la voiture
devient orpheline et le rattrapage de fin de boucle la ramène au domicile.

C'est un compromis explicite : ce seuil **augmente mécaniquement le taux de véhicules
orphelins**, donc la pression sur l'alarme correspondante. Le bon réflexe est de lire le
taux, pas de relever le seuil d'alarme pour la faire taire.

---

## [2026-08-02] Les enfants vont à l'école en voiture — sans la conduire

Un agent qui ne peut pas conduire peut désormais **monter** dans la voiture du foyer, à
condition qu'il y ait une voiture et quelqu'un pour la conduire. Un adulte sans permis
vivant seul n'est donc pas concerné.

**Avant :** 480 trajets en voiture étaient conduits par des agents de moins de 18 ans,
dont 310 par des moins de 14 ans, et 197 par des personnes sans permis. En prime, la
voiture se garait à l'école, et l'enfant était ensuite sommé de la ramener.
**Après :** plus personne ne conduit sans l'âge et le permis. L'enfant se déplace toujours
en voiture — l'enquête EMC² compte le passager dans « voiture », la part modale reste donc
comparable — mais la voiture ne se gare plus à destination : elle repart avec son
conducteur, et aucun retour n'est forcé.

Le persona décrit maintenant la situation telle qu'elle est (« se déplace en voiture
uniquement en passager·ère, conduit·e par un adulte du foyer ») au lieu d'un vague
« voiture dispo ».

Version 1, assumée : le trajet d'accompagnement du parent n'est pas généré. On rend la
voiture accessible à l'enfant, rien de plus.

---

## [2026-08-02] Les mineurs de la population synthétique n'ont plus le permis

131 des 165 mineurs de la population de 1 000 personnes portaient un permis de conduire,
dont 86 enfants de moins de 14 ans. Les agents « Scolaire » cumulaient des activités
`work` là où on attendait `education`, et un écolier de neuf ans arrivait au modèle avec
un motif de déplacement « Travail » et une journée domicile → travail → domicile → loisir.

La cause est un appariement statistique qui perdait l'âge : le vivier de donneurs était
réduit au seul département de la Haute-Garonne, les strates devenaient trop petites, et le
critère d'âge était le premier abandonné. Un enfant héritait alors d'un donneur adulte —
avec son permis et son emploi du temps. Un `bool(nan)` valant `True` en Python faisait le
reste : toute personne non appariée recevait le permis.

**Avant :** 131 mineurs avec permis, 50 activités `education` pour ~150 scolaires.
**Après :** 0 mineur avec permis, 219 activités `education`.

Deux livrables, parce que les deux sont nécessaires :

- des **garde-fous dans la chaîne de génération** (vivier national restauré, âge placé en
  tête des critères d'appariement, valeurs manquantes traitées comme « non », permis de
  mineurs exclus du calcul de disponibilité de la voiture, pas de VAE avant 14 ans) — ils
  ne prendront effet qu'à la prochaine régénération complète, qui exige des données hors
  dépôt ;
- un **correctif de surface** applicable tout de suite à une population existante, avec les
  mêmes garanties d'usage que les autres scripts d'enrichissement : `--dry-run`, écriture
  en place, idempotent.

Ce que le correctif de surface ne fait pas, et qu'il redit à chaque exécution : les chaînes
d'activités restent celles de donneurs adultes. Renommer `work` en `education` ne rapproche
pas l'école du domicile.

---

## [2026-08-01] La campagne de calibration se met en pause — et le dit tous les matins

La campagne de calibration de prompt (branche 7, itération 39/50, meilleur composite
24,98) est **volontairement à l'arrêt** sur la VM cloud. Le daemon et le digest quotidien
sont coupés, y compris au redémarrage de la machine : plus une seule éval, plus un seul
jeton de quota Gemini consommé. Rien n'est perdu — le store SQLite garde la lignée
complète et la reprise repartira exactement au point d'arrêt.

Une pause silencieuse est une pause qu'on oublie. Un rappel Discord part donc **chaque
matin à 10:00 (heure de Paris)** tant que la campagne est désactivée : « prompt
calibration désactivé », avec la commande de reprise. Il n'appelle aucun modèle et ne lit
pas le store, donc il ne coûte rien.

**Avant :** couper la campagne, c'était couper aussi le seul canal qui donnait de ses
nouvelles — au bout de trois jours plus personne ne savait si elle tournait encore.
**Après :** l'arrêt est explicite et se rappelle à toi tous les matins jusqu'à ce que tu
le lèves.

Deux commandes suffisent, depuis le PC : **`make pause`** coupe la campagne et arme le
rappel, **`make start`** coupe le rappel et relance la campagne. Les deux sont
idempotentes, et `make pause` réinstalle au passage les unités systemd depuis le dépôt —
il n'y a plus rien à copier à la main sur la VM.

Reprendre ne coûte rien tant que le quota du jour est épuisé : le daemon relit le délai
de reprise persisté dans le store et se rendort au lieu de taper l'API — vérifié au
redémarrage (`💤 dodo 8.0 h`).

`make cloud-deploy` respecte désormais la pause : il ne redémarre le daemon que si
celui-ci est encore armé. Avant, sa recette faisait un `restart` inconditionnel, qui
relance un service arrêté — déployer un correctif pendant une pause réveillait la
campagne sans le dire.

---

## [2026-07-31] La page de synthèse change de run — et cesse de pouvoir mentir dessus

La page décrit désormais le run du 31 juillet, celui qui tourne avec la cohérence de
chaîne des véhicules et le trait de type de logement. Deux axes qui affichaient zéro
depuis leur mise en place se remplissent enfin : la **ventilation par type de logement**
(302 individuel isolé, 219 petit collectif, 211 grand collectif, 143 individuel accolé)
et les **couronnes de résidence** mesurées depuis l'hypercentre unifié — à population
identique, 30 personnes changent de couronne, dans les deux sens, ce qui est la signature
d'un centre déplacé de 820 m et non d'un seuil bricolé.

Changer le run de référence était jusqu'ici une manœuvre à laquelle on ne pouvait pas se
fier. Le cache d'évaluations était indexé sur le nom du jeu et les paramètres du modèle,
**sans le run** : épingler un nouveau run resservait donc la mesure du précédent, que le
script réétiquetait avec le descriptif du nouveau. Aucun appel payé, des composites
identiques au centième, et un fichier affirmant décrire 383 décisions d'un run tout en en
portant 762 d'un autre. Rien, dans la page, ne l'aurait signalé.

Deux verrous posés :

- **la clé de cache porte l'empreinte de ce qui est réellement soumis au modèle** —
  couples (personne, texte gelé de la requête). Deux runs ne peuvent plus partager une
  entrée ; relancer sur le même run reste gratuit ;
- **la page écarte une mesure faite sur un autre run que celui qu'elle épingle**, et sa
  carte le dit en toutes lettres au lieu de la faire voisiner en silence avec les volets
  calculés sur le bon substrat.

Les évaluations déjà payées n'ont pas été perdues : elles ont été ré-indexées sur
l'empreinte de leur run d'origine, si bien qu'un retour au run du 29 juillet ne coûte
aucun appel.

**Avant :** changer de run épinglé produisait une page d'apparence cohérente dont un
volet sur trois décrivait un autre run, sans aucun signal
**Après :** la mesure du volet 2 est refusée tant qu'elle ne porte pas sur le run épinglé,
et le cache ne peut plus la resservir d'un run à l'autre

État à ce jour : volets 1 (simulation, 6 333 décisions / 881 personnes) et 3 (modèle
PROGEDO, 6 333 décisions scorées) régénérés sur le nouveau run ; volet 2 en attente de sa
mesure — les deux clés Google ont épuisé leur quota journalier, reprise le 1er août à
09:00 CEST avec `make common-set-eval` (≈ 111 appels), puis `make synthesis`.

---

## [2026-07-31] La voiture aussi reste là où on l'a garée

Le vélo avait cessé de se téléporter la veille ; la voiture, elle, était toujours
disponible partout et tout le temps. Il suffisait d'en posséder une pour pouvoir
démarrer depuis n'importe quel point de la ville — y compris un bureau où on était
arrivé en tram. C'était, sur le mode qui pèse le plus lourd dans les parts modales, le
même véhicule fantôme que celui corrigé pour le vélo.

**Le véhicule est désormais un lieu**, vélo et voiture traités à l'identique par trois
règles :

- **On ne conduit que ce qui est là.** Un mode véhiculé n'est proposé que si l'agent
  possède le véhicule *et* qu'il est garé à son point de départ.
- **Le véhicule suit celui qui l'utilise.** Il se déplace avec l'agent qui le prend, et
  reste sur place sinon. Le vélo laissé au bureau n'est plus réputé retrouvé à la maison
  le soir — c'était le dernier vestige de téléportation de la version précédente.
- **On ramène son véhicule chez soi.** Sur un trajet de retour au domicile partant d'un
  lieu où le vélo ou la voiture est garé, les options sont restreintes à ce mode. C'est
  un filtre sur les itinéraires candidats, pas une décision : **aucun appel LLM
  supplémentaire**, et si les deux véhicules sont là, le choix reste au LLM.

Un agent qui part travailler à vélo n'a donc plus de voiture au bureau à midi, et il
rentre à vélo le soir. Les deux véhicules ne peuvent plus être « quelque part » en même
temps.

**Avant :** posséder une voiture suffisait à pouvoir la prendre depuis n'importe où ;
un vélo laissé au travail réapparaissait au domicile en fin de journée.
**Après :** chaque véhicule a une position, qui contraint les modes offerts au départ et
impose le retour en fin de boucle.

**Ce qui reste approximé, et mesuré comme tel.** Une étape intermédiaire contourne le
verrou de retour : domicile → travail en voiture, travail → sport à pied, sport →
domicile en bus laisse la voiture au travail. Ces orphelins sont ramenés au domicile — un
agent privé de sa voiture pour tout le reste de la simulation serait un biais bien pire —
mais comptés, avec une alarme `[ALARME]` si le rattrapage dépasse 5 % des retours au
domicile. Non traité non plus : la voiture est un bien du ménage mais sa position est
suivie par personne, et le park-and-ride reste hors de portée du modèle par trajet.

`vehicle_chain_enabled=false` rétablit l'ancien comportement, pour mesurer l'effet sur
les parts modales à population égale.

---

## [2026-07-31] La calibration tient hors de son jeu d'entraînement (action A4)

Le volet 2 n'avait jusqu'ici qu'un seul type de chiffre : celui mesuré sur le jeu qui a
servi à **optimiser** les prompts. Un composite d'entraînement ne distingue pas un prompt
qui a compris la population d'un prompt qui a mémorisé ses 298 personas — et le store ne
portait strictement aucune évaluation sur le jeu de test. Vérifié avant de payer quoi que
ce soit : zéro éval « test » dans les deux stores, et les trois évals « val » qui
existaient dataient d'un autre modèle, donc inutilisables.

La lignée épinglée est désormais mesurée **entière** — six nœuds sur six, pas seulement
ses extrémités — sur les 106 décisions du jeu de test, sous le régime de production.

**Ce que « généralisation » veut dire ici, et la page le dit en toutes lettres.** La
question n'est pas rhétorique : un découpage par personne soutient « des individus jamais
vus », un découpage par déplacement seulement « d'autres trajets des mêmes individus ».
La réponse est établie sur les fichiers eux-mêmes, pas sur la foi de la règle déclarée :
le découpage est **par personne**, et les 66 personnes du test n'apparaissent dans aucun
des 298 personas du train. C'est bien l'affirmation forte. Au passage, le jeu de
screening est au contraire entièrement inclus dans le train — ce qui lui interdit ce
rôle, et explique qu'on ne l'ait pas utilisé.

**Le résultat, et il aurait été lu à l'envers sans son témoin.** Lu brut, l'écart
ressemble à du surapprentissage : la graine passe de 24,35 à 31,60, la feuille de 22,24 à
24,06. Il n'en est rien. Les divergences par strate sont biaisées vers le haut à petits
effectifs, et le train porte 298 personnes contre 66 pour le test. Le témoin le chiffre
sans un seul appel LLM, en rejouant le score des décisions **déjà stockées** du train sur
200 sous-ensembles de 66 personnes : 29,84 pour la graine, 26,90 pour la feuille. La
seule réduction d'effectif coûte donc +5,49 et +4,66 points — du même ordre que les +5,02
mesurés la veille sur la simulation. À effectif neutralisé, la feuille est **meilleure**
sur le test que sur le train (−2,84), et les six nœuds tombent dans la bande du témoin :
**aucun surapprentissage détectable**.

**Le gain survit ; son amplification n'est pas démontrée, et la page ne la revendique
pas.** Entre la graine et la feuille, la calibration gagne 2,12 points sur le train et
7,54 sur le test. Tentant d'en conclure que le prompt calibré généralise mieux qu'il
n'apprend — sauf qu'un second témoin, apparié celui-là (les deux prompts scorés sur les
*mêmes* personnes tirées, donc bien moins bruyant), place le gain d'entraînement à +2,94
sur une bande allant de −1,84 à +8,24. Les 7,54 y tombent. Ce qui est acquis, c'est que
le gain **n'était pas un artefact du jeu qui a servi à l'obtenir** ; le reste demanderait
plus de 66 personnes.

**Une confusion résiduelle est publiée plutôt que tue.** Le moteur retire délibérément la
section « Historique » — la mémoire du run source, non reproductible — des jeux de
retenue, alors qu'elle couvre 86 % des records du train. Le prompt de test n'est donc pas
seulement adressé à d'autres personnes : il est aussi plus court d'une section. Les deux
effets sont mêlés, rien dans les données ne les sépare, et la page l'écrit.

Ces chiffres ne rejoignent ni la trajectoire, ni la lignée, ni la matrice comparative : le
jeu de retenue est un troisième substrat, et coller une colonne de 66 personnes à côté de
colonnes de 881 rejouerait exactement la confusion corrigée la veille. La matrice y
renvoie, elle ne l'absorbe pas.

**Avant :** le volet 2 ne savait dire que ce que valaient ses prompts sur le jeu qui les
avait produits — aucune manière de distinguer un progrès réel d'une mémorisation.
**Après :** un score hors échantillon, sur des individus jamais vus, accompagné des deux
témoins qui empêchent de le lire de travers et de l'aveu de ce qu'il mêle encore.

Coût : 98 appels LLM pour les six nœuds (~34 pour les seules extrémités). Reprise par
nœud, gratuite depuis le cache.

---

## [2026-07-31] Le gain de la calibration se transporte, son niveau non (action A3)

La matrice « Synthèse comparative » alignait cinq colonnes comme si elles se comparaient. Elles
ne se comparaient pas : la simulation était scorée sur le run épinglé, la calibration sur ses
**personas gelés** — un sous-ensemble d'un run de deux semaines plus tôt. Deux mesures faites
sur deux populations, présentées côte à côte, avec la même échelle de couleurs.

La page l'avoue désormais colonne par colonne, au lieu de le noyer dans un paragraphe de bas de
section : sous la matrice, chaque colonne déclare son substrat et, pour la calibration, le nœud
et le régime de mesure exacts. Le volet 2 gagne aussi un tableau qui met les deux chiffres d'un
même prompt face à face — son composite sur le jeu commun et son composite sur les personas
gelés — parce que ce sont deux nombres différents et que le lecteur doit savoir lequel il lit.
Le bloc « avant / après » historique porte maintenant son substrat dans son titre.

La mesure est faite : `make common-set-eval` a rejoué la graine et la feuille de la lignée
épinglée sur un échantillon **du run**, sous le régime épinglé, avec une couverture de 100 %
(80 personnes sur 80). L'échantillon est gelé et reproductible — tirage par personne, jamais par
trajet, sur un hachage stable de l'identifiant : 509 décisions, 80 personnes. C'est le plus petit
tirage dont toutes les strates de l'enquête atteignent l'effectif minimal ; en dessous, des
tranches d'âge se vident et le score cesse d'être comparable à celui de la simulation. Le
hachage est volontairement dans un espace distinct de celui du découpage train/val/test, sans
quoi l'échantillon n'aurait contenu que des personas ayant servi à optimiser la lignée.

La commande ne redécoupe pas les lots elle-même : elle passe par l'évaluateur du moteur, donc par
les défenses posées la veille contre les réponses amputées de personas. Bien lui en a pris —
**29 lots sur 128 sont revenus incomplets**, jusqu'à 2 personas rendus sur 8, tous rattrapés par
re-tir en moitiés. Une boucle de lotissement réécrite pour l'occasion aurait scoré sur une
sous-population sans que rien ne le signale.

**Le résultat, et il n'est pas flatteur.** Le gain de la calibration **se transporte** : entre la
graine et la feuille, 2,13 points de composite sur le jeu commun contre 2,12 sur les personas
gelés. Le progrès mesuré sur le jeu d'entraînement était donc réel, et pas un artefact de son
propre instrument. Mais le **niveau**, lui, ne se transporte pas du tout : les deux prompts
passent de 24,35 et 22,24 sur les personas gelés à **38,53 et 36,41** sur le jeu commun. Le même
texte, mesuré par le même modèle sous la même politique, est ~14 points moins fidèle dès qu'on
change de population.

**Une partie de cet écart n'a rien à voir avec les prompts, et la page le chiffre au lieu de le
supposer.** Les divergences par strate sont biaisées vers le haut quand les effectifs sont
petits : mesurer sur 81 personnes n'est pas mesurer sur 881. Une nouvelle colonne, « Sim.
(éch. V2) », restreint la simulation **aux mêmes 81 personnes** — sans un seul appel LLM — et
montre que la simulation passe alors de 24,37 à 29,39. Soit **+5,02 points pour la seule
réduction d'effectif**, à décisions inchangées. C'est à cette colonne que la calibration doit
être comparée, et non à celle du run entier. Elle reste au-dessus : sur le même substrat et à
effectif égal, le volet 2 est moins fidèle à l'enquête que la simulation.

**Ce que le quota a appris.** Le seau journalier du free tier Google ne se réinitialise pas à
minuit UTC mais à **minuit Pacific**. Plus retors : une sonde de quatre appels a réussi sur une
clé pourtant épuisée avant que le compteur ne rattrape — l'application du quota journalier n'est
pas exacte à la frontière, et aucun petit test ne dit de façon fiable si un seau est ouvert. La
mesure a finalement coûté 175 appels sur la seconde clé.

**Avant :** cinq colonnes d'apparence homogène, dont deux portaient en réalité sur une autre
population, et un avertissement générique en fin de section.
**Après :** sept colonnes, chacune annonçant sa population, son effectif et son régime de
mesure — dont un témoin de taille qui rend l'écart du volet 2 lisible au lieu de le laisser
attribuer au prompt.

---

## [2026-07-31] Le volet « modèle statistique » entre enfin dans la comparaison (action A8)

La matrice de la page de synthèse portait une colonne « Modèle » entièrement vide. Le modèle
existait pourtant, entraîné et sérialisé la veille — mais il n'avait jamais rencontré une seule
décision du run qui sert de jeu commun. Il la remplit désormais, et il faut lire ce chiffre en
sachant ce qu'il est.

**Ce qui a été mesuré.** La politique statistique est appliquée aux 5 945 décisions du run
épinglé — exactement le périmètre du volet 1, construit par le même code et les mêmes
exclusions, sinon les colonnes ne se compareraient pas davantage qu'avant. Pour chaque
déplacement, les 21 variables du contrat sont reconstruites depuis le persona, la chaîne
d'activités et la géographie, puis le modèle prédit une distribution sur quatre modes.

**La correction qui change tout : l'offre réellement proposée.** Le modèle prédit sur quatre
modes sans savoir lesquels étaient disponibles ; la simulation, elle, ne choisit que parmi les
itinéraires calculés pour ce trajet-là. Sans correction, on reprocherait au LLM de n'avoir pas
choisi un mode qu'on ne lui a jamais offert. Chaque prédiction est donc restreinte aux modes
proposés, puis ramenée à 100 %. L'effet n'est pas décoratif : 3,4 % de la masse prédite tombait
en moyenne sur des modes indisponibles, la correction déplace le mode le plus probable sur 142
décisions, et rapproche les parts modales de l'enquête de 17,9 à 14,1 points d'écart cumulé.

**Deux lectures, et il faut les deux.** Comme pour la simulation, la page rapporte la masse de
probabilité et le mode effectivement retenu. L'écart entre les deux est structurel : le modèle
calibre bien le vélo en masse mais ne l'élit presque jamais. N'afficher que la première le
flatterait, n'afficher que la seconde le condamnerait.

**Le modèle écrase les deux autres volets, et c'est attendu.** Il est entraîné sur l'enquête qui
sert ici de cible : sa victoire ne dit rien de la qualité relative du LLM, elle borne ce qu'un
modèle purement statistique atteint sur ce jeu. L'avertissement est désormais posé juste
au-dessus de la matrice, là où le lecteur voit le chiffre, et non trois sections plus loin.

**Deux surprises, rapportées telles quelles.** Aucune décision n'a dû être écartée : on
attendait environ 5 % de trajets hors du périmètre d'enquête, la population de ce run tombe
intégralement dedans — les 5 % avaient été mesurés sur un autre tirage de population. Et 15,5 %
des décisions n'ont pas de catégorie socioprofessionnelle : la population simulée utilise un
libellé « Retired » que le recodage de l'enquête ne produit jamais. Il est laissé manquant
plutôt que rapproché à l'aveugle d'une catégorie voisine — l'occupation principale, elle, porte
bien « Retraité ».

**Avant :** colonne « Modèle » entièrement « n. d. » ; rien dans la page ne situait le modèle
face à la simulation ou à la calibration.
**Après :** deux colonnes remplies sur les sept dimensions, mesurées sur le même run et avec la
même loss que les autres, assorties du cadrage qui empêche de les surinterpréter.

---

## [2026-07-31] Le modèle oubliait des personas, et personne ne le voyait (action A10)

Depuis la bascule vers les comptages pondérés, ré-évaluer une lignée de prompts « n'avançait
plus ». Aucune erreur, aucun message : la commande tournait et rien ne progressait. La cause
supposée — une sortie cinq fois plus longue qui dépasserait le délai d'attente de 240 s de
l'appel Gemini — était fausse. Les mesures l'ont écartée en trois appels.

Ce que l'instrumentation a montré, sur des lots réels : **3,6 à 8,8 secondes** par appel pour
une limite de 240 s, **`finishReason=STOP`** partout, **2 742 tokens** de complétion au pire
pour un plafond de 4 096. Ni lenteur, ni troncature. Le vrai défaut est ailleurs et bien plus
gênant : à 15 personas par requête, **le modèle rend un JSON valide, conforme, complet de son
point de vue — mais qui ne contient que 5 à 8 des 15 personas demandés.** Quatre lots sur
douze étaient ainsi amputés, soit 18 % de la population perdue en silence.

Aucune défense existante ne pouvait le voir : ce n'est ni une erreur réseau, ni une réponse
tronquée, ni un JSON hors-schéma. Le lot passait pour un succès, le score était calculé sur
la population restante, et **mis en cache comme s'il était complet**. Une mesure fausse, donc,
plutôt qu'une mesure absente — le pire des deux.

Trois défenses ont été posées :

- **on compare désormais ce qui a été demandé à ce qui a été reçu**, persona par persona, à
  chaque requête ;
- **un lot incomplet est re-tiré par moitiés.** Redemander la même chose à un modèle réglé en
  décodage déterministe redonne la même réponse : il faut réduire la demande, pas insister. Un
  lot revenu à 5 personas sur 15 est ainsi complété à 15 sur 15 en trois appels ;
- **une évaluation dont la couverture reste insuffisante est refusée**, pas stockée. La base ne
  garde pas le nombre de personas réellement vus : un score calculé sur 60 % du jeu y serait
  indiscernable d'un score complet et fausserait toute la trajectoire. Un nœud déclaré
  « manquant » dit la vérité ; un score partiel, non.

L'échec silencieux proprement dit est refermé au passage : la boucle de nouvelles tentatives
rendait une liste vide quand elle s'épuisait, que l'appelant prenait pour un lot légitimement
sans décision. Elle lève maintenant, avec une alarme. Et les trois grandeurs qui ont permis le
diagnostic — tokens produits, raison d'arrêt, latence — sont tracées à chaque appel Gemini et
rappelées dans le texte de chaque erreur, pour que la prochaine panne de ce genre se lise au
lieu de se deviner. Une série de réponses tronquées lève désormais une alarme explicite, une
seule par épisode.

**Avant :** la lignée de prompts n'était lisible que sous `mistral-small-latest` et l'ancienne
politique « mode élu » — ni le modèle de production, ni la politique courante. La page de
synthèse le signalait par un avertissement, et la campagne de calibration ne pouvait pas
reprendre.
**Après :** les six nœuds de la lignée sont mesurés sous le régime épinglé —
`gemini-3.1-flash-lite-preview` et la politique « masse de probabilité », c'est-à-dire le
modèle et la politique de la production. L'avertissement de repli a disparu de la page, qui
affiche désormais la lignée sous **deux** instruments en regard.

Et cette double lecture dit quelque chose : **les deux régimes voient la lignée s'améliorer.**
Sous l'ancien (mistral, mode élu), la calibration gagnait 7,60 points, soit 24,9 % du niveau
de la graine ; sous le nouveau, 2,12 points, soit 8,7 %. Près de trois fois moins en part,
mais **dans le même sens**. Le progrès n'était donc pas un artefact de l'instrument qui avait
servi à l'optimiser — ce qu'on ne pouvait pas exclure jusqu'ici. Son *ampleur*, en revanche,
ne se transporte pas : le chiffre à retenir est celui du régime de production.

---

## [2026-07-31] La référence statistique existe enfin (action A6)

La page de synthèse compare trois façons de décider d'un mode de transport. La troisième —
un modèle statistique entraîné sur l'enquête EMC² 2023 — n'était jusqu'ici qu'une
intention : le jeu de données et le contrat de variables existaient, le modèle non. Il
existe maintenant, il se rejoue en une commande (`make policy`), et il est reproductible à
l'octet près.

Ce que ce volet apporte, ce n'est pas un concurrent loyal : entraîné sur l'enquête qui sert
aussi de cible, il est proche de l'oracle sur les parts modales, et c'est exactement son
intérêt — il **borne** ce qu'un modèle purement statistique atteint, et situe les deux
autres volets par rapport à cette borne. Sur son propre jeu de test (étanche au ménage,
pondéré par les coefficients de redressement de l'enquête) : log-loss 0,5363, 79,5 %
d'accuracy, et 2,1 points d'écart cumulé sur les parts modales — vélo, voiture, transports
collectifs et marche tombent tous à moins de 1,1 point de l'observé.

Trois pièges pouvaient produire un modèle spectaculaire et faux, tous refermés par une
vérification explicite plutôt que par une intention :

- **la distance déclarée trahit le mode.** Pour la marche, elle est une fonction affine de
  la durée : l'utiliser, c'est donner la réponse. Les trois variables concernées sont
  marquées « diagnostic » dans le contrat, et l'entraînement refuse de démarrer si l'une
  d'elles entre dans le modèle ;
- **le découpage train/test doit rester étanche au ménage** — les déplacements d'un même
  foyer partagent son équipement automobile. Il est lu tel quel dans le jeu de données,
  jamais retiré au hasard, et l'arrêt de l'entraînement se règle sur une part détourée
  dans l'apprentissage, jamais sur le test ;
- **les parts modales n'ont de sens que redressées.** La pondération de l'enquête pèse
  l'entraînement et toutes les métriques rapportées.

Le modèle est livré comme un artefact autoportant : il embarque l'ordre de ses variables,
l'encodage de chaque modalité, l'ordre de ses classes, la version du contrat et ses propres
métriques. Qui veut l'utiliser n'a rien à relire des micro-données d'enquête, ni rien à
deviner.

**Avant :** le volet 3 de la page de synthèse affichait « aucun modèle entraîné », et ses
sept dimensions étaient vides.
**Après :** la page montre le modèle, ses métriques de test et ses parts modales prédites
face aux observées. Les sept dimensions **restent vides** : le modèle n'a encore été
appliqué à aucune décision du jeu commun d'évaluation, et c'est l'action A8 qui produira
ces prédictions. La comparaison des trois volets attend donc toujours.

---

## [2026-07-30] Un seul centre-ville pour toute la chaîne (action A9)

Le projet portait deux centres de Toulouse distants de 820 m : celui que l'enquête EMC²
publie dans le contrat de variables (centroïde des zones du secteur Capitole) et un second
codé en dur dans le journal des déplacements. C'est ce dernier qui décidait si un agent
habitait « Toulouse » ou en « 1re couronne ». Résultat : les agents de la bande
intermédiaire changeaient de couronne selon qu'on les regardait par le journal ou par les
variables du modèle statistique, et les deux lectures du lieu de résidence ne se
comparaient plus.

Le centre n'est plus déclaré nulle part au runtime : il est **lu** dans
`feature_spec.json`, par le même point de lecture qui sert déjà au résolveur de zone fine
à refuser une couche dont le centre diverge du modèle. Une définition, un seul endroit qui
la lit — la divergence ne peut plus revenir par recopie.

Le fichier de spécification vient des micro-données PROGEDO, d'accès restreint : sur un
poste qui ne les a pas, il est simplement absent. Ce cas est prévu et tracé dans les logs,
et le repli est la valeur publiée du spec recopiée en constante, jamais l'ancien centre
abandonné. Un test échoue si le repli et le spec se mettent à diverger.

**Avant :** les couronnes de résidence du journal étaient mesurées depuis 43.6047 / 1.4442,
les distances au centre du modèle depuis 43.597347 / 1.444997.
**Après :** les deux depuis 43.597347 / 1.444997, la valeur calculée sur les données de
l'enquête.

⚠ **Les runs déjà archivés ne bougent pas.** La couronne est calculée au moment où le
déplacement est journalisé, puis écrite dans `moves.csv` ; la page de synthèse relit cette
colonne, elle ne la recalcule pas. Le volet 1 affiche donc exactement les mêmes chiffres
qu'avant sur le run épinglé. Seuls les runs postérieurs à ce changement porteront les
couronnes du centre unifié.

---

## [2026-07-30] Le point sait dans quelle zone il tombe (action A7)

Le modèle statistique de choix modal s'appuie sur quatre variables géographiques qui
pèsent lourd dans ses décisions — distance origine-destination, densités, distances au
centre. Toutes supposent de savoir dans **quelle zone fine** de l'enquête EMC² tombe un
point. L'enquête le donne ; la simulation, elle, n'a que des coordonnées. Cette
information manquait : le volet « modèle » de la page de synthèse ne pouvait pas être
calculé, faute de pouvoir reconstituer ses propres variables d'entrée.

Le rattachement existe maintenant, et il rejoue **la formule d'entraînement**, pas une
approximation raisonnable. Deux pièges étaient sur le chemin :

- **La distance.** En simulation on connaît les coordonnées exactes, donc la tentation est
  de mesurer la distance à vol d'oiseau. Ce serait faux : à l'entraînement la distance est
  mesurée entre **centroïdes de zones**, avec une valeur imputée pour les trajets qui
  restent dans une seule zone. Mesuré sur la population : 1,29 km contre 0,65 km sur ces
  trajets-là, soit un facteur 2 — et ce sont exactement les trajets courts où marche, vélo
  et voiture se disputent la décision.
- **Le centre-ville.** Le projet en portait deux définitions distantes de 820 m. Le
  résolveur n'en redéclare aucune : il lit la distance au centre déjà calculée avec le
  centre publié, et refuse de démarrer si la couche et le modèle n'en décrivent pas le
  même (l'action A9 reste ouverte côté `move_logger.py`).

Hors du périmètre d'enquête, rien n'est deviné. Les points concernés sont à 22,8 km en
médiane de la zone la plus proche : ce sont des communes franchement extérieures, pas des
cas limites. Le résolveur renvoie « pas de zone » et laisse l'appelant basculer sur sa
politique de repli. Une alarme se déclenche si le taux hors couche s'envole au-delà de
15 %, signe que la population ou la couche a changé de périmètre.

**Avant :** les six variables géographiques du modèle n'étaient calculables qu'à
l'entraînement ; en simulation, aucune.
**Après :** calculables sur **95,1 %** des paires origine-destination de la population de
référence (95,5 % des localisations), à l'identique de l'entraînement.

⚠ **Ce que cela ne fait pas.** Rien ne prédit encore : le modèle lui-même reste à
entraîner (A6) et à appliquer au jeu commun (A8), et rien n'est branché sur la simulation.
A7 lève le préalable, elle ne produit aucun chiffre de choix modal.

Une nuance à garder en tête pour la suite : 81 des 785 zones n'ont aucun ménage enquêté,
donc pas de densité. Elles concernent 5,5 % des paires exploitables. La valeur est laissée
**manquante**, jamais remplacée par zéro — « aucun ménage enquêté » et « zone déserte » ne
sont pas la même information, et le modèle sait traiter une valeur absente.

---

## [2026-07-30] Le vélo ne se téléporte plus : cohérence de chaîne

Un agent parti travailler en bus retrouvait son vélo pour repartir du bureau. Le vélo
n'était filtré que sur la **possession** (`personal_bike`), jamais sur sa présence
effective là où l'agent se trouve. Résultat : un vélo fantôme, disponible à chaque étape
de la journée quel que soit le mode des trajets précédents.

Le vélo est désormais proposé si l'agent en possède un **et** l'a avec lui : il le suit
quand le trajet est fait à vélo, il est retrouvé au retour au domicile, il reste au point
de départ sinon. Un agent qui n'a pas bougé (même localisation) garde son vélo.

**Avant :** vélo proposé sur 3191 des 5956 trajets d'un run de référence, dont 352 avec un
vélo laissé ailleurs → 18,2 % de part modale vélo (cible enquête EMC² 2023 : 4 %).
**Après :** ces 352 trajets ne peuvent plus être faits à vélo, soit **−5,9 points** de part
modale (18,2 % → 12,3 % en borne haute). Une partie du report devrait aller à la marche,
sous-représentée à 7,7 % contre 26,8 % attendus — l'écart se corrige donc des deux côtés.

Ce qui n'est **pas** traité, et reste à faire pour combler l'écart restant : le vélo est
encore proposé sans plancher d'âge (45 % des moins de 11 ans « possèdent » un vélo, 18,2 %
de leurs trajets se font à vélo) et jusqu'à 30 km à vol d'oiseau. Version simple assumée
côté chaîne : un vélo laissé au travail est réputé retrouvé au domicile le soir.

---

## [2026-07-30] Une trajectoire de calibration lisible bout à bout (action A5, entamée)

⚠ **A5 n'est pas terminée.** Ce qui suit outille la lecture d'une lignée sous un régime
unique et l'affiche ; le **rejeu** que l'action demande n'a produit **aucune évaluation**
(voir « ce qui reste bloqué » plus bas). La page marque donc l'action « partiellement
faite », garde son coût et continue de la compter en attente — un nouvel état, introduit
justement parce que livrer le code d'une mesure n'est pas produire la mesure.

La page de synthèse traçait la calibration en facettant par **modèle d'évaluation**, et
prévenait qu'on ne devait pas lire ces courbes bout à bout. C'était insuffisant sur deux
points, et la page le dit maintenant autrement.

**Un modèle ne suffit pas à définir un régime de mesure.** Le moteur a basculé du « mode
élu par persona » à la masse de probabilité : sous cette politique, les décisions
elles-mêmes changent, donc aucun recalcul de loss ne réconcilie deux évals qui ne la
partagent pas. La page regroupe désormais par **modèle · politique** — deux clés d'API sur
le même modèle restant, elles, une seule courbe. La plage de composite d'un store porte sur
son seul régime de référence, au lieu de mélanger les instruments dans un même intervalle.

**Une courbe chronologique ne dit pas qu'une calibration a progressé.** Elle mêle des
branches et des nœuds sans parenté. La page affiche donc en plus une **lignée** — la chaîne
des mutations acceptées, de la graine à la feuille, épinglée dans `sources.yaml` comme l'est
le run du jeu commun. Sur les 6 nœuds de la lignée retenue, le composite descend de 30,52 à
22,92, soit **−24,9 % d'écart à l'enquête EMC²**, sans changement d'instrument en cours de
route. C'est la seule trajectoire de la page qui se lise comme l'effet du prompt.

Ces 6 nœuds étaient **déjà** mesurés sous un régime unique, dans le store, depuis juillet :
il n'a fallu aucun appel LLM pour le voir — seulement cesser de confondre « modèle » et
« régime », et savoir reconstruire la chaîne. Le régime en question est cependant
`mistral-small-latest` et l'ancienne politique « mode élu » : ni le modèle épinglé, ni la
politique courante. C'est là que l'action reste ouverte.

Reconstruire cette chaîne demandait un détour : les prompts étant adressés par contenu, un
texte déjà produit sur une autre branche est réutilisé avec le parent de sa *première*
création — souvent aucun. Chaîner par le seul champ `parent` s'arrêtait donc au deuxième
nœud et **perdait la graine**, c'est-à-dire la référence à laquelle toute la trajectoire se
compare. La lignée est maintenant reconstruite par les arêtes de mutation.

Nouvelle commande `calibrate reeval` pour rejouer une lignée sous un régime unique : elle
annonce son coût en appels avant de le payer (`--dry-run`), ne paie que les nœuds manquants,
et reprend où elle s'est arrêtée après un épuisement de quota.

**Ce qui reste bloqué (action A10).** Porter cette lignée sur le modèle d'évaluation
*épinglé* n'a pas abouti : sous la politique pondérée, aucune éval ne termine. Les lots
dépassent le timeout de 240 s de l'adaptateur Google et sont retentés cinq fois sans qu'une
seule erreur ne remonte au journal. Réduire les lots de 15 à 8 personas n'a pas suffi. Le
blocage ne concerne pas que cette mesure : **aucune campagne n'a encore tourné sous cette
politique**, donc la prochaine reprise rencontrera le même mur.

**Avant :** les courbes de calibration étaient facettées par modèle, avec l'avertissement de
ne pas les lire bout à bout — et aucune trajectoire ne pouvait l'être
**Après :** une lignée de 6 prompts se lit d'un bout à l'autre sous un régime unique, et le
mélange des régimes est nommé pour ce qu'il est — mais sous un modèle qui n'est pas celui de
la production, et l'action reste comptée en attente

---

## [2026-07-30] Le jeu commun de la page de synthèse est épinglé (action A1)

La page de synthèse lisait son run de référence à travers `experiments/current`, un symlink
qui bouge à chaque simulation. Deux régénérations pouvaient donc décrire deux substrats
différents — mêmes titres, mêmes tuiles, chiffres incomparables — sans que rien ne l'indique.
Le manifeste épingle désormais un chemin d'archive explicite
(`experiments/archive/2026-07-29_18_34`). La tuile « Run » affiche l'état de l'épinglage et
avertit si le chemin configuré se résout ailleurs.

Épingler ne change aucun chiffre : la comparaison des deux `data.json` ne montre que la
nouvelle information d'épinglage et l'horodatage. C'est bien le but — le run décrit était le
bon, il n'était simplement pas garanti de le rester.

Évaluer un autre run reste immédiat, sans toucher au manifeste :
`make synthesis RUN=experiments/archive/<run>`.

La liste d'actions en bas de page conserve maintenant ce qui a été fait : A1 y apparaît barrée
et marquée « faite », avec ce que sa réalisation a produit, et le titre compte les huit actions
restantes. Les identifiants ne sont jamais recyclés — les avertissements de la page et les
tickets y renvoient par numéro. La version précédente de la page est archivée sous
`docs/synthesis/archive/2026-07-30_1037/`.

**Avant :** la page suivait le dernier run en date ; régénérer après une simulation changeait
silencieusement le jeu d'évaluation
**Après :** le run est nommé dans le manifeste et vérifiable par empreinte ; changer de jeu
commun est un acte explicite

---

## [2026-07-30] Page de synthèse : les trois approches face à l'enquête EMC²

Une page HTML autonome (`make synthesis`) rassemble pour la première fois au même endroit
la fidélité des parts modales simulées à l'enquête CEREMA — globalement **et** dans chaque
sous-catégorie : âge, genre, occupation, motif, distance, lieu de résidence. Elle compare
trois approches : la simulation actuelle (le LLM donne des probabilités, la simulation tire
au sort), la calibration de prompt, et le modèle statistique PROGEDO.

Le point qui rend la comparaison possible : les trois volets sont ramenés à une même trame
de décision, puis scorés par **la loss du moteur de calibration elle-même**, importée et non
réécrite. Seule la pénalité de longueur de prompt est neutralisée — elle n'a pas de sens pour
un volet sans prompt. Le substrat commun est un run de simulation, seul terrain qui porte à
la fois les personas complets, les jeux de choix OTP et les coordonnées dont le modèle
statistique a besoin.

Deux constats sortent immédiatement des chiffres. La simulation **sous-estime massivement la
marche** (7,5 % contre 26,8 % attendus) et surestime le vélo (18,8 % contre 4,1 %) : 47 points
d'écart L1 cumulé, le plus gros gisement d'amélioration identifié à ce jour. Et le recalcul de
l'historique de calibration montre que l'écart spectaculaire entre les scores archivés
(~176 contre ~42) n'était **pas** un progrès : c'étaient deux loss différentes. Ramenés à la
même mesure, les deux régimes se recouvrent.

La page ne masque pas ce qui manque : chaque donnée absente devient une carte « Données
manquantes » portant le chemin attendu et l'action qui la produirait. Le volet PROGEDO est
aujourd'hui entièrement dans ce cas, et neuf actions chiffrées sont listées en bas de page.

**Avant :** la fidélité à l'enquête se reconstituait à la main, notebook par notebook, sans
score commun entre la simulation et la calibration
**Après :** `make synthesis` produit la page complète et son JSON en quelques secondes, avec
les sources tracées (chemin, date, empreinte)

---

## [2026-07-30] La calibration mesure à nouveau le prompt de production

La calibration évalue les prompts sur des jeux gelés, extraits de vrais runs — donc rendus
avec les étapes d'itinéraire en puces de même niveau que les options (cf. l'entrée
suivante). Les 803 personas des jeux `v1` sont **tous** concernés : la mesure exposait donc
le modèle juge à la même renumérotation, et une part des personas était comptée avec une
répartition uniforme qu'aucun prompt n'avait produite. Autrement dit : du bruit qui
pénalisait indifféremment toutes les variantes, et pouvait faire accepter une mutation
neutre.

Le traitement des options de la production est désormais appliqué à la mesure : étapes
ré-indentées en sous-puces au moment de construire le lot (le jeu sur disque n'est pas
touché, rien à re-geler) et probabilités hors bornes réalignées sur leur mode. Le drapeau
`prod_option_handling` (défaut : activé) pilote les deux et entre dans la clé de cache
d'éval : les deux régimes ne se mélangent jamais dans le store, et `false` restaure
l'ancien comportement pour reprendre une campagne sur ses évals déjà payées.

**Avant :** une part des personas notée « au hasard » par construction, mêmes prompts,
scores bruités
**Après :** la mesure porte sur le prompt réellement servi en simulation

Bonne nouvelle de calendrier : aucune éval n'avait encore été payée sous le régime de
comptage pondéré actuel — le changement de clé ne coûte donc pas un seul appel LLM.

---

## [2026-07-30] Les étapes d'un itinéraire ne sont plus lues comme des options

Dans le prompt d'itinéraire, chaque option était suivie du détail de ses étapes (« Marche
jusqu'à… », « Bus '401' vers… ») en puces de **même niveau** que la ligne d'option. Plusieurs
modèles (mistral, llama 3.1, gemma) comptaient donc ces étapes comme des options
supplémentaires et renumérotaient tout le bloc : 36 « options » là où 6 étaient proposées.
Leurs probabilités partaient sur des index inexistants, silencieusement écartés — et quand
tout le vecteur y passait, la décision du modèle était remplacée par un tirage **uniforme**
entre les 6 itinéraires. Une voiture choisie à 100 % devenait « un mode au hasard ».

Les étapes sont désormais des sous-puces indentées « · », l'en-tête annonce le nombre
d'options et la plage d'index, et la consigne précise que seules les lignes `- [n]` sont des
options — et que les index repartent de 0 pour chaque persona du lot. En second rideau, une
entrée dont l'index est hors bornes est replacée sur l'option que **son libellé de mode**
désigne au lieu d'être jetée ; si plusieurs options partagent ce mode, la masse est répartie
entre elles (la part modale, qui est la mesure, reste exacte). Ce qui n'est pas rattrapable
sort maintenant en `make error` sous `[ALARME]` au lieu de se fondre dans les warnings.

**Avant :** 12 agents sur 36 touchés décidaient à l'uniforme ; part modale mesurée à 0,41
d'écart de la décision réelle du modèle
**Après :** 1 seul repli uniforme, écart ramené à 0,02 — rejoué sur le run du 2026-07-29

Effet secondaire utile : moins de bruit dans les logs. Les entrées hors bornes à probabilité
nulle — l'essentiel des 299 warnings du run de 5 h 40 du 2026-07-29 — passent en `DEBUG` ;
ne restent visibles que les pertes de masse réelles.

---

## [2026-07-29] `make run` retrouve le modèle GAMA après le déplacement du dépôt

Le dépôt a été déplacé sous `~/Documents/Projects/`, mais deux endroits pointaient encore
sur l'ancien emplacement : le `Makefile` et le workspace GAMA lui-même. Résultat, `make run`
lançait GAMA sur un dossier inexistant — l'IHM s'ouvrait sur un projet mort, et le lancement
finissait en exception SWT.

Le chemin en dur du `Makefile` est remplacé par une racine déduite de l'emplacement du
`Makefile` : déplacer à nouveau le dépôt ne cassera plus rien. Le lien du projet
`CityTransport` enregistré dans `~/Gama_Workspace` a été repointé sur le bon dossier.

**Avant :** `make run` ouvrait GAMA sur un workspace inexistant, exception au démarrage
**Après :** le modèle `City.gaml` se charge, plus aucune erreur au lancement

---

## [2026-07-29] Un jeu d'entraînement sain pour le choix modal — la distance ne trahit plus le mode

Première brique d'une politique de choix modal statistique, destinée à servir de bras de
comparaison face à l'agent LLM (les agents non-LLM se contentent aujourd'hui de prendre la
première option proposée). Le jeu d'entraînement est construit depuis l'enquête EMC²
Toulouse 2023, mais **sans la variable de distance de l'enquête**.

Cette distance était contaminée : pour la marche, elle n'est pas mesurée mais recalculée
depuis la durée déclarée du trajet (58 m/min, exactement). Un modèle entraîné dessus
devinait donc le mode en connaissant déjà la réponse. Elle est remplacée par une distance
entre zones, indépendante du mode, et calculable aussi bien dans l'enquête qu'en cours de
simulation — là où, au moment du choix, il n'existe pas encore de « distance du trajet »
mais plusieurs itinéraires candidats ayant chacun la sienne.

**Avant :** prédiction quasi parfaite de la marche (PR-AUC 0.985) — signature d'une fuite
**Après :** 0.804 sur une distance honnête, et un modèle utilisable en simulation

Le jeu est pondéré par les coefficients de redressement de l'enquête, découpé par ménage
(et non par déplacement, qui laisserait fuir un individu des deux côtés), et accompagné
d'un contrat de features versionné : chaque variable retenue doit être calculable à
l'instant de la décision en simulation, sinon elle est exclue quel que soit son pouvoir
prédictif. Sur ce jeu, les parts modales prédites s'écartent de 3,3 points cumulés des
parts observées, sans aucune repondération artificielle des classes.

Domaine de validité déclaré : l'enquête ne couvre que les **jours ouvrés** et le seul
périmètre où les deux zones du déplacement sont enquêtées.

---

## [2026-07-29] La calibration mesure la valeur des blocs par simple omission

Savoir quel bloc du prompt porte le score se paie en évaluations. La campagne le faisait
par **valeurs de Shapley** : des centaines de coalitions de blocs par passe, recalculées
après chaque acceptation — le poste de dépense le plus lourd du quota journalier, pour un
chiffre dont on n'utilise en pratique que le **classement**. Le réglage
`attribution_method` revient au calcul simple : retirer chaque bloc à tour de rôle et
mesurer ce qu'on perd. Shapley reste disponible en option, pour les moments où la
répartition exacte du gain compte (blocs redondants ou synergiques).

**Avant :** une passe d'attribution ≈ 2 + 25 × 11 = **277 coalitions** à évaluer
**Après :** 1 + 11 = **12 coalitions** — soit ~23× moins, à budget de quota constant

Aucune évaluation déjà payée n'est perdue : les deux méthodes partagent le même cache
adressé par contenu, et les coalitions « prompt complet moins un bloc » leur sont
communes. Repasser à `attribution_method: shapley` réutilise donc tout ce qui a été
mesuré entre-temps.

---

## [2026-07-29] La calibration ne mesure plus le hasard

Le score d'un prompt se calculait en tirant au sort une décision par persona, puis en
comptant les résultats. Sur ~800 personas, ce tirage dispersait chaque part modale
d'environ **±1,7 point** — assez pour noyer une amélioration réelle du prompt, ou pour
faire accepter par chance une mutation sans effet, qui orientait ensuite toute la
campagne.

Le modèle annonçant désormais « voiture 60 %, bus 40 % », il n'y a plus rien à tirer :
on compte directement 0,6 voiture et 0,4 bus. Le score devient **exactement** la
prédiction du prompt, sans le moindre aléa. Deux évaluations du même prompt donnent le
même chiffre.

**Avant :** relancer une évaluation changeait le score de ±1,7 point par mode
**Après :** score identique au chiffre près — un écart de 1 point est un vrai écart

Le tirage au sort reste évidemment en place là où il a un sens : dans la simulation, où
il fait qu'un habitant ne prend pas sa voiture 180 jours d'affilée. Utile pour simuler
un individu, nuisible pour mesurer une population.

Deux conséquences pratiques : `eval_samples` (le nombre de tirages destinés à lisser ce
bruit) **n'a plus d'objet** et n'entre plus dans la clé de cache ; et les effectifs de
strate comptent désormais des **personnes**, non des lignes — les seuils d'exclusion des
petites strates sont donc mécaniquement plus exigeants. L'historique d'évaluations reste
relisible : une décision d'avant la bascule vaut un poids de 1.

---

## [2026-07-29] Détecter le jour où le modèle confond ses options

Le LLM recopie, à côté de chaque probabilité, le mode de l'option concernée. Cette
redondance est maintenant vérifiée : si le modèle annonce « 80 % — la voiture » sur une
option qui est en réalité un bus, ce n'est pas une faute d'étiquette, c'est le signe
qu'il a mélangé les options — et que **tous** ses pourcentages sont attribués aux
mauvaises lignes. Une simulation entière pouvait tourner sur des résultats faux sans que
rien ne l'indique.

Le taux d'incohérence est exposé dans Grafana (attendu : 0 %) et déclenche une alarme
au-delà de 5 % sur 200 options observées. Côté calibration, le mode de chaque option est
désormais lu dans le jeu d'évaluation lui-même plutôt que dans la réponse du modèle : la
mesure ne dépend plus de ce qu'il déclare.

Le dashboard mobilité gagne une section « répartition attendue vs tirée » : ce que le
modèle voulait, ce que les agents ont fait, et l'écart entre les deux.

---

## [2026-07-29] La calibration ne s'arrête plus faute de quota au bout de 27 itérations

Après chaque amélioration retenue, la boucle de calibration recalculait la contribution
de **chaque** bloc du prompt par valeur de Shapley — une attribution exacte, mais qui
consommait à elle seule le quota journalier : la campagne 7 s'est arrêtée après 27
itérations sur 200 prévues.

L'attribution se fait désormais par **omission** (retrait bloc à bloc, `N+1` évaluations
au lieu de ~25 fois plus). C'est moins exact — deux blocs redondants y paraissent tous
deux inutiles — mais le classement des blocs reste bon, et c'est tout ce que le ciblage
des mutations utilise. Shapley reste disponible (`attribution_method: shapley`) pour une
analyse ponctuelle hors boucle, et les deux méthodes partagent le même cache : basculer
de l'une à l'autre ne jette aucune évaluation déjà payée.

**Avant :** une passe d'attribution ≈ 25 × N évaluations → quota épuisé en une journée
**Après :** N+1 évaluations, budget prévisible → la boucle tourne jusqu'au bout

---

## [2026-07-29] Les agents ne suivent plus l'avis du LLM, ils tirent leur mode au sort

Le LLM ne désigne plus l'itinéraire optimal : il note **chaque** option proposée par la
probabilité que ce persona la retienne (somme = 100), et l'agent tire son mode dans cette
distribution. Un persona qui hésite entre voiture (60 %) et bus (40 %) ne prend plus
systématiquement sa voiture : à l'échelle de la population, les 40 % de bus existent enfin.

Le post-traitement projette ces probabilités sur une liste **fermée** de modes (marche,
vélo, voiture, transports collectifs, train, deux-roues motorisé) : un mode qu'aucune
option ne propose — la marche quand le trajet est trop long — apparaît explicitement à
**0 %** au lieu de disparaître, ce qui rend les répartitions comparables d'un agent et
d'un jour à l'autre.

Le cache sémantique conserve désormais **la distribution, pas la décision**. Un cache hit
rejoue donc un tirage : le même agent, replacé dans le même contexte un autre jour, peut
prendre le bus là où il prenait sa voiture — sans le moindre appel LLM. La graine du
tirage dérive de `(agent.mode_draw_seed, agent, activité, jour simulé)` : un run relancé
reproduit exactement les mêmes trajets, et changer `mode_draw_seed` explore un autre
tirage sans repayer d'inférence.

Chaque demande d'itinéraire trace sa répartition dans `moves.csv`, **une colonne par
mode** (`P(Marche) %`, `P(Voiture Privée) %`, …) : on peut comparer ligne à ligne ce que
le LLM estimait et ce que l'agent a fait, et agréger les parts modales attendues sans
reparser quoi que ce soit. Un `0` signifie « mode explicitement écarté », une cellule vide
« décision sans répartition » (mono-choix, erreur LLM, cache hérité).

Côté calibration de prompt, l'évaluation applique la même politique — et les
`eval_samples` tirages proviennent maintenant d'un **seul** appel LLM : une éval `train`
coûte 33 requêtes au lieu de 99, à nombre de décisions scorées identique.

**Avant :** un persona = un mode figé ; un cache hit rejouait éternellement la même décision
**Après :** un persona = une distribution ; chaque cache hit retire un mode, la répartition
attendue est visible dans `llm_mode_probability_pct_total`

⚠ Deux invalidations attendues : le texte des prompts système ayant changé, le **cache LLM
repart d'un répertoire neuf** (il est isolé par empreinte de prompt), et les évaluations de
calibration déjà payées ne sont plus réutilisables.

---

## [2026-07-28] La boucle cesse d'ordonner au mutateur de s'entêter

Un rejet annoté `Δ=+9.89` — le candidat **aggrave** l'écart de 23 % — était classé
« bruit statistique », catégorie dont la consigne associée est « l'idée n'est pas
invalidée, garde le levier ». La boucle demandait donc de persévérer sur une piste que
la mesure venait de réfuter. En campagne 7, cinq itérations consécutives ont reformulé
le même levier sur le même bloc, pour rien.

Les rejets sont désormais triés par **ampleur** : au-delà de 10 % du score courant, un
échec devient `[dégrade]` et déclenche la consigne inverse — abandonner le levier, pas
le reformuler. En dessous, rien ne change : une amélioration non significative reste une
piste ouverte.

**Avant :** `Δ=+9.89` et `Δ=+0.30` recevaient la même consigne
**Après :** les dégradations franches disent « change d'hypothèse », les Δ marginaux
disent toujours « reformule »

---

## [2026-07-28] Le prompt d'optimisation ne peut plus enseigner ce qu'il interdit

La règle « jamais de seuil chiffré du type *marche si moins de 2 km* » n'était qu'une
phrase adressée au modèle : rien ne l'appliquait. Un bloc contenant exactement cette
règle avait donc été accepté, puis **capitalisé comme meilleur argument de la
bibliothèque** (gain 134.4), puis re-servi à chaque itération comme exemple à imiter.

La contrainte est maintenant appliquée en code, avant toute évaluation, et les arguments
capitalisés qui la violent sont écartés — y compris ceux déjà stockés, sans avoir à
toucher aux bases existantes. La *mention* d'un nombre reste permise : « la règle des
48 heures » passe, « moins de 2 km » non.

**Pourquoi ça compte :** un seuil chiffré fait du choix de mode un automatisme. Le
prompt cesse alors de simuler un raisonnement de déplacement et encode la réponse
attendue — il colle au jeu d'évaluation et ne vaut plus rien en simulation.

---

## [2026-07-28] Le bloc à modifier est choisi par calcul, plus par le modèle

Désigner le bloc de prompt le plus nuisible n'est pas un jugement : c'est un maximum sur
des grandeurs déjà mesurées (contribution Shapley, poussée modale, strates fautives).
Ce choix est passé du modèle au code, ce qui libère de la place dans le prompt et rend
la décision reproductible.

Un bloc rejeté deux fois de suite sort maintenant du jeu des cibles pour trois
itérations. L'ancien garde-fou ne bloquait que la répétition d'un **texte** proche,
jamais l'acharnement sur une **cible** — c'est ce qui laissait un même bloc monopoliser
la campagne pendant que des blocs nuisibles jamais essayés attendaient leur tour.

**Avant :** cinq itérations d'affilée sur `consigne_s3`
**Après :** ce bloc passe en cooldown et la cible bascule sur le bloc nuisible suivant

---

## [2026-07-28] Mutation en deux temps : diagnostiquer, puis rédiger

Le prompt d'optimisation demandait au modèle d'analyser ses échecs, de choisir sa cible
et d'écrire le texte dans le même souffle, avec tout le contexte servi d'un bloc. On
peut désormais scinder : un premier appel diagnostique le bloc visé et produit une
directive courte (il lui est interdit d'écrire le texte), un second rédige sous cette
directive sans revoir l'appareil analytique.

Chaque appel est nettement plus court : le plus long passe de 15 600 à 6 800 caractères,
et les **deux réunis** coûtent moins que l'appel unique d'avant. L'appel supplémentaire
se paie sur le quota du modèle de mutation, distinct de celui de l'évaluation.

Désactivé par défaut (`decomposed_mutation`), pour être comparé au fonctionnement
historique à budget d'évaluation égal plutôt que substitué en silence.

**Avant :** un appel de ~15 600 caractères qui fait tout
**Après :** deux appels spécialisés, 0,57× le coût en texte, ablatables séparément

---

## [2026-07-27] Le pré-tri par un second modèle est abandonné

Mesure décisive : sur 23 mutations d'un même prompt, le modèle léger pressenti pour
pré-trier les candidats **ne retrouve pas du tout le classement du juge de référence**
(corrélation de rang −0,01, soit l'équivalent d'un tirage au sort). L'idée d'essayer
plusieurs mutations par itération et de laisser un modèle bon marché désigner la
meilleure est donc écartée.

Ce résultat corrige une mesure antérieure encourageante (corrélation 0,76), obtenue
sur des prompts très différents les uns des autres. Départager des variantes franches
est facile ; départager des candidats **voisins** — la seule chose utile pour un
pré-tri — ne fonctionne pas.

**Avant :** on envisageait 3 ou 4 candidats par itération avec pré-sélection automatique
**Après :** un seul candidat par itération, comme aujourd'hui ; le second modèle reste
utile uniquement pour *générer* les mutations, ce qui libère déjà le quota du juge

---

## [2026-07-27] Nouvelle pénalité de longueur : tolérance puis coût exponentiel

La pénalité de longueur peut désormais prendre une forme à seuil : **nulle jusqu'à
une taille de prompt jugée acceptable** (350 mots par défaut), puis croissante de
façon exponentielle au-delà. Dans la zone de tolérance, deux prompts ne sont plus
départagés que par la qualité de leur prédiction ; au-delà, le coût devient vite
prohibitif, ce qui empêche le prompt de s'allonger sans fin.

Rejouée sur les 173 évaluations déjà en base, la correction remet le classement à
l'endroit : le prompt vidé de ses instructions passe du 1ᵉʳ au 7ᵉ rang, et le
meilleur devient un prompt de 7 blocs et 179 mots. La corrélation entre longueur et
score tombe de 0,81 à 0,02 — la longueur cesse d'être un critère de sélection.

**Avant :** un prompt de 335 mots encaissait 16,75 points de pénalité d'entrée
**Après :** 0 point tant qu'il reste sous le seuil ; 2 points à 500 mots, 20 à 650

L'ancienne forme linéaire reste disponible et reste le défaut ; la nouvelle
s'active par `length_penalty_mode: exp_tolerance`. Le changement ne coûte aucun
appel LLM et n'invalide aucune évaluation déjà payée.

---

## [2026-07-27] La calibration optimisait la brièveté plus que la justesse

Le meilleur prompt du store s'est avéré être… le prompt vide. En décomposant la
métrique, la cause est identifiée : la **pénalité de longueur** pèse autant que le
terme de fidélité aux parts modales, et représente environ 40 % de la variation
totale du score.

Or la taille du prompt n'a **aucun effet mesurable sur la qualité de prédiction**
(corrélation de rang −0,03 sur 173 évaluations, non significative) : les
répartitions de modes prédites sont quasi identiques du prompt vide au prompt
complet. Tout ce que le score retenait de la longueur venait de la pénalité.

Recalculé sans elle, le classement s'inverse : le meilleur prompt passe de 1 bloc
à 7 blocs, et les deux classements ne se ressemblent qu'à moitié.

En revanche — et contrairement à ce qu'on pouvait attendre — ce n'est **pas** ce qui
bloque la campagne en cours (19 mutations, 0 acceptée). Vérification faite sur les
couples avant/après disponibles : toutes les mutations proposées *raccourcissent* le
prompt, donc la pénalité les avantage, et toutes dégradent quand même la prédiction.
Annuler la pénalité n'en sauverait aucune. Le blocage vient du générateur de
mutations, qui ne produit que des candidats moins bons.

**Avant :** le score récompensait surtout les prompts courts
**Après :** le diagnostic est posé et chiffré ; le dosage de la pénalité reste à trancher

Le réglage se teste **sans aucun appel LLM** (`make backtest`) : les décisions brutes
sont conservées et le dosage de la pénalité n'entre pas dans la clé de cache.

---

## [2026-07-27] Analyse Shapley sur la marche — et une fuite de données dans ProGEDO

Un troisième notebook, `scripts/progedo_logit/explore_progedo_walk_shapley.ipynb`, applique à
la **marche** le protocole du notebook vélo. Il en ressort deux choses : un avertissement sur
les données, et un diagnostic inverse de celui du vélo.

### Deux variables ProGEDO sont inutilisables pour la marche

Les premiers modèles atteignaient une PR-AUC de **0.98** contre un taux de base de 0.31 —
aucun modèle de choix modal ne prédit un comportement social à ce niveau. La cause est
identifiée : **`D11`, documentée comme distance à vol d'oiseau, n'est pas mesurée pour les
déplacements à pied. Elle vaut exactement `durée déclarée × 58 m/min`.** Rapport constant à 58
sur tous les quantiles, ~250 valeurs distinctes contre ~9 800 pour la voiture, corrélation avec
la géographie réelle de 0.40 pour la marche contre 0.995 pour les autres modes. La variable
n'encode pas une distance : elle encode la cible. `D12` (distance sur le réseau du mode
utilisé) est contaminée pour la même raison.

Le notebook les remplace par une distance reconstruite depuis le shapefile des zones fines,
identique quel que soit le mode. La PR-AUC retombe alors à une valeur crédible.

**Avant :** PR-AUC marche = 0.985, artefact de mesure
**Après :** PR-AUC marche = 0.804 (baseline) à 0.855 (41 variables), sur une distance
origine-destination mode-neutre

⚠️ **Le notebook vélo utilise `D11` et est donc concerné** : sa PR-AUC de 0.410 est
probablement surestimée, les trajets à pied y étant identifiables à coup sûr. Le classement
SHAP reste vraisemblablement valide. Un rejeu avec la distance corrigée est à faire.

### La marche est contrainte, le vélo est choisi

Une fois la fuite corrigée, enrichir le persona n'apporte presque rien à la marche : **×1.06**
contre ×1.78 pour le vélo. La marche est décidée par la géométrie du déplacement, et se
modélise sans persona riche pourvu que l'agent dispose d'une distance origine-destination
correcte.

À 2 km ou moins — là où les quatre modes sont plausibles et où un levier a un sens — les
déterminants apparaissent : le **motif** (le loisir pousse à marcher, le travail non), la
**disponibilité d'une voiture** (même variable clé que pour le vélo, et même sens : les modes
actifs se décident contre la voiture), le **nombre de voitures par titulaire du permis**, le
**type d'habitat** (la maison isolée décourage la marche) et le **stationnement nocturne de la
voiture** — quand la reprendre coûte une place au retour, on marche. L'âge joue en U : 72 % de
marche chez les 17–25 ans, 70 % chez les 75 ans et plus, 57 % chez les 40–60 ans.

Comme pour le vélo, la catégorie grossière `car_availability` ne pèse presque rien (0.021)
quand le comptage fin en pèse dix fois plus : **l'agrégation en catégories détruit le signal**.

### Conséquence pour la mémoire de l'agent

Les habitudes déclarées ne captent que **11,1 % de l'importance SHAP** pour la marche, contre
28,6 % pour le vélo. La lecture doit rester prudente — `P19`, la fréquence d'usage de la
marche, est *intégralement vide* dans le fichier Toulouse 2023, donc l'habitude piétonne n'a
pas été mesurée. Mais le fait solide tient : les variables exogènes **suffisent** pour la
marche. La mémoire long terme est un levier pour le vélo, pas pour la marche — inutile de
dépenser du budget de contexte à raconter l'historique piéton d'un agent.

---

## [2026-07-27] Un second modèle pourrait pré-trier les candidats — sous réserve

Mesure : sur 27 versions de prompt déjà notées par le modèle juge, un second modèle
plus léger retrouve **le même classement à 76 %** (corrélation de rang de 0,758).
De quoi écarter l'hypothèse qu'il jugerait au hasard.

Ce n'est pas encore une validation. L'intervalle de confiance va de 0,53 à 0,89 :
il reste environ 30 % de chance que la vraie valeur soit sous le seuil retenu (0,70).
Et le test portait sur des prompts très différents entre eux, alors que la tâche
réelle consiste à départager des variantes proches — donc plus difficile. Le
pré-tri automatique n'est pas activé ; une seconde mesure sur des mutations réelles
tranchera.

À noter aussi : les notes des deux modèles diffèrent de 3 points en moyenne, un
écart comparable à leur dispersion. Le second modèle peut servir à *classer*, jamais
à produire une note versée dans la campagne.

La mesure n'a rien coûté au budget du juge (ses 27 notes venaient du cache) et n'a
touché aucune évaluation existante.

---

## [2026-07-27] Le modèle d'évaluation restera sur son nom actuel

Test direct sur l'API Google : le nom `…-flash-lite-preview` utilisé par la calibration
et le nom `…-flash-lite` **désignent le même modèle** — Google redirige l'un vers
l'autre. Renommer donnerait donc des résultats identiques tout en jetant toutes les
évaluations déjà payées. L'opération est écartée : coût pur, bénéfice nul.

La note de référence précise aussi que le jeu `screen` est un **échantillon gelé de 17 %
de `train`**, et qu'il sert à deux phases différentes (attribution Shapley et tri des
mutations) — une distinction qui manquait et qui rendait les chiffres d'activité de la
campagne difficiles à interpréter.

---

## [2026-07-27] Note de référence sur les quotas, et check_phase0 réparé

Une note `prompt_calibration/docs/quotas-et-modeles.md` chiffre ce que coûte
réellement une journée de calibration : une évaluation complète mobilise 297 requêtes,
soit **la totalité du quota quotidien d'un modèle**. C'est ce qui explique le rythme
d'environ une évaluation complète par jour. Le document liste aussi les quatre réglages
à ne jamais modifier sans précaution — ceux qui rendraient inutilisables toutes les
évaluations déjà payées.

Le script `check_phase0.py` ne démarrait plus depuis que la calibration est devenue un
dépôt autonome : ses imports pointaient vers l'ancienne arborescence. Il retrouve aussi
seul le répertoire d'expérience, que les deux dépôts soient imbriqués (poste de dev) ou
côte à côte (VM cloud), et affiche un message clair au lieu d'une trace quand il ne
trouve rien.

**Avant :** `check_phase0.py` s'arrêtait sur `ModuleNotFoundError`
**Après :** il tourne et confirme 100 % des sections rattachées (436 agents)

---

## [2026-07-27] Mutation et évaluation sur deux quotas Gemini séparés

La calibration disposait de 500 requêtes Gemini par jour, partagées entre l'évaluation
(le juge qui mesure la qualité d'un prompt) et la mutation (qui propose les variantes à
tester). Chaque mutation mangeait donc du budget d'évaluation. La mutation bascule sur
`gemini-3.5-flash-lite`, un modèle distinct doté de **son propre compteur de 500
requêtes/jour** : le juge garde désormais son quota entier.

Le modèle d'évaluation, lui, ne bouge pas — en changer invaliderait toutes les
évaluations déjà payées et rendrait les scores incomparables. Le cache est intact
(91 évaluations sur la base cloud, 194 en local, toutes toujours servies).

Le plafond de débit passe aussi de 15 à 12 requêtes/minute : le tableau de bord Google
montrait des pics à 18/min, donc des refus (429) en cours de campagne.

**Avant :** 500 requêtes/jour pour évaluer *et* muter ; pics de débit en dépassement
**Après :** 500 requêtes/jour dédiées à l'évaluation + 500 pour la mutation ; plus de dépassement

---

## [2026-07-25] Pourquoi le vélo est mal prédit : analyse Shapley sur ProGEDO élargi

Un second notebook, `scripts/progedo_logit/explore_progedo_bike_shapley.ipynb`, cherche les
variables qui expliquent réellement le choix du **vélo** — le mode que le modèle de choix
modal prédisait le plus mal. Là où le notebook de production ne retient que les traits
*communs* avec le persona LLM, celui-ci ratisse un maximum de variables ProGEDO et laisse
une analyse de Shapley trancher. Le notebook de production reste inchangé et comparable.

Le diagnostic est confirmé : le vélo souffrait de **variables manquantes**, pas seulement de
sa faible part modale (3,9 %).

**Avant :** 15 variables, PR-AUC vélo = 0.230
**Après :** 42 variables exogènes, PR-AUC vélo = 0.410 — **×1.78 à modèle et protocole
identiques**. 15 des 25 premières variables du classement SHAP étaient absentes du modèle.

Ce qui pèse, par ordre d'importance : la **disponibilité d'une voiture pour le trajet
domicile-travail** (le vélo se choisit contre la voiture), le **nombre de vélos par personne**
du ménage (l'ancien booléen `has_bike` détruisait cette information), la **géographie**
(densité et distance au centre, à l'origine comme à la destination — un axe totalement absent
jusqu'ici), la **saison** (5,05 % de vélo en septembre contre 3,05 % en février) et le
**niveau d'études** (de 0,17 % à 5,90 % de part vélo).

Deux enseignements contre-intuitifs. Le stationnement vélo au domicile, déterminant canonique
dans la littérature, finit 38ᵉ sur 42 : 79 % des ménages toulousains en disposent, la variable
ne discrimine pas. Et le stationnement voiture au travail **s'inverse** une fois les autres
variables contrôlées — son effet brut était porté par des corrélats, pas par lui-même.

Enfin, un résultat qui porte sur l'architecture de l'agent plutôt que sur les données : en
ajoutant les **habitudes déclarées** (fréquence d'usage du vélo, de la voiture, des TC), la
PR-AUC monte à 0.601 et la fréquence d'usage du vélo devient la première variable du modèle,
devant la distance. Cinq variables captent 28,6 % de l'importance totale. Une part
substantielle du signal vélo n'est donc pas structurelle mais **habituelle** — elle réside
dans l'historique de la personne, c'est-à-dire précisément ce que la mémoire long terme de
l'agent est censée porter. Un agent sans mémoire des trajets passés a un plafond de
performance sur le vélo, quelle que soit la richesse de son persona.

Métrique employée : PR-AUC (et non l'accuracy, sans signification à 3,9 % de positifs),
séparation train/test **par ménage** pour éviter qu'un même individu figure des deux côtés.

---

## [2026-07-25] Jeu ProGEDO prêt pour régression logistique (choix modal)

Un notebook extrait de l'enquête ProGEDO 2023 (EMC² Toulouse) un CSV directement exploitable
en **régression logistique multinomiale du choix modal**, en n'utilisant **que les paramètres
communs** avec le persona du projet (`traits_json`) — ou rendus communs par recodage vers le
même espace de valeurs. Une ligne = un déplacement (l'unité de décision de l'agent), la cible
est le mode `car/bike/walk/transit` (aligné sur `_primary_mode`).

Les features couvrent le persona statique (âge, sexe, taille du ménage, permis, abonnement TC,
nombre de voitures, disponibilité voiture, présence de vélo, catégorie socioprofessionnelle,
occupation, emploi/études) et le contexte de décision (motif, distance, heure de départ).
`income` et `employment_sector` sont exclus (absents de ProGEDO) ; `personal_bike` est réduit à
`has_bike` car les vélos électriques (M22) ne sont pas renseignés dans ce jeu.

Le notebook fait import → merge (déplacement + personne + ménage) → recodage → nettoyage
(modes hors champ, non-enquêtés, valeurs critiques manquantes) → séparation features/cible →
export, et se termine par un contrôle sklearn qui ajuste le CSV tel quel.

**Avant :** les CSV ProGEDO bruts (codes SAS, une table par niveau) n'étaient pas alignés sur
le vocabulaire du persona ni structurés pour un modèle de choix modal.
**Après :** `scripts/progedo_logit/progedo_mode_choice.csv` (~54 500 déplacements, 15 features +
cible) prêt à charger, plus les variantes `_X.csv` / `_y.csv`.

---

## [2026-07-24] Calibration : notifications Discord détaillées (« où en est la campagne »)

Les notifications du daemon de calibration disaient **qu'il** travaillait, jamais **où il
en était** : entre « Daemon démarré » et « Quota épuisé », des heures de silence, sans
savoir s'il en était à la dixième ou à la deux-centième coalition Shapley. Le salon
Discord suit désormais la campagne **étape par étape**.

Au **démarrage** de chaque passe, un message « d'où l'on part » : itération de reprise et
cible, meilleur composite connu, prompt courant (score, nombre de mots, blocs mutables),
tailles des jeux train/val/screening, modèle d'éval et nombre de coalitions Shapley
attendues. À l'**arrêt** (quota épuisé ou budget atteint), le message symétrique : l'étape
exactement interrompue, le travail de la passe (itérations, acceptées/rejetées, évals
payées vs servies par le cache, appels LLM, durée) et le gain de composite obtenu.

Entre les deux, les **étapes principales** sont annoncées (éval initiale, proposition de
mutation, gate de strate, screening, paliers de racing, éval complète, attribution
Shapley, validation, compaction), chaque **itération** publie sa mutation puis son verdict
(composite, Δ, cause de rejet), et un **battement de cœur** (toutes les 15 min par défaut)
donne l'avancement *à l'intérieur* d'une étape longue — c'est lui qui répond à « il en est
où, sur ses 250 valeurs de Shapley ? ».

**Avant :** « 🟢 Daemon démarré » … 6 h de silence … « ⏸️ Quota épuisé — reprise demain 07:00 »
**Après :** « ▶️ Passe démarrée — itération 11 → 50, best 36.80 » … « 🔷 Shapley (init) 253
coalitions attendues » … « ⏳ Avancement — Shapley 124/253 (49 %), 87 payées, 37 cache » …
« ⚖️ Itération 12 → accepted, composite 34.20 (Δ=-2.60) » … « ⏸️ Quota épuisé pendant :
attribution Shapley après acceptation #5 · 168/253 (66 %) — 3 itérations, 412 évals payées »

Réglable dans la config du run (`notify_stages`, `notify_iterations`,
`notify_heartbeat_seconds`, `notify_min_interval_seconds`) ; sans webhook Discord, rien ne
change et rien n'est envoyé.

---

## [2026-07-23] Calibration : notifications Discord & digest quotidien

Le daemon de calibration autonome peut désormais **remonter son état sur un salon
Discord**, pour suivre une campagne cloud sans SSH. Un webhook (pas de bot) reçoit
**uniquement les transitions d'état** : démarrage, quota épuisé → mise en veille (avec
l'heure de reprise), reprise après reset, **nouveau meilleur prompt**, fin de campagne.
Deux ajouts qui ciblent des angles morts : une alerte **⚠️ quand un 429 n'est pas
identifié « per day »** (le cooldown retombe alors sur un délai court — signe que le
libellé Gemini a peut-être changé), et une alerte **☠️ « daemon mort »** portée par
systemd (`OnFailure=`), seul moyen de prévenir en cas de crash/OOM où plus aucun message
applicatif ne peut partir.

Nouveau `calibrate digest` (timer systemd quotidien) : un **récapitulatif lisible**
(itération, meilleur composite, évals payées et mutations acceptées sur 24 h, veille en
cours) **reformulé par Mistral** — modèle distinct du quota d'éval Gemini, donc **sans
entamer le budget** de la campagne ; repli sur un texte brut si Mistral est indisponible.

Le tout est **best-effort et opt-in** : sans `DISCORD_WEBHOOK_URL` dans `~/calib.env`,
aucune notification n'est émise (no-op) ; un envoi qui échoue n'interrompt jamais la
campagne (le store SQLite reste la source de vérité). Aucun contenu de prompt ni clé
n'est transmis — seulement des métriques agrégées.

**Before :** campagne cloud silencieuse — il fallait `journalctl -u calib` en SSH pour
savoir si elle avançait, dormait ou était morte.
**After :** l'essentiel arrive sur Discord (veille/reprise/best/fin/échec) + un digest
quotidien ; la supervision SSH devient optionnelle.

---

## [2026-07-23] Calibration : daemon autonome & cooldown quota (24h/reset)

La calibration de prompt peut désormais tourner **entièrement seule sur le cloud** et
exploiter au mieux le quota journalier (RPD/TPD). À l'épuisement du quota, les requêtes
LLM sont **mises en veille jusqu'à la réouverture du quota** — la durée est lue dans le
429 du provider, avec une subtilité : pour un quota **journalier** (marqueur `PerDay`),
le délai renvoyé par Gemini sous-estime le temps réel jusqu'au reset, donc on vise le
**prochain minuit Pacific** (`quota_reset_tz`, DST géré) pour reprendre pile sur le quota
frais. Le cooldown est **persisté dans le store** (portée globale), donc il survit à un
redémarrage.

Nouveau mode `calibrate run --loop` : un **daemon** qui dort pendant le cooldown
(heartbeat `💤` dans les logs) puis reprend seul — plus besoin de cron. Une unité systemd
(`cloud/calib.service`) le maintient en vie (démarrage au boot, redémarrage après crash).
Le lancement cron one-shot reste supporté et bénéficie de la même **garde de démarrage**
(il sort proprement si un cooldown est encore actif au lieu de re-solliciter l'API).

**Avant :** quota épuisé → le run s'arrêtait ; il fallait un cron externe pour rejouer,
et une relance trop tôt re-tapait l'API avant le reset.
**Après :** `run --loop` sous systemd → la campagne consomme le quota du jour, se rendort
jusqu'au reset, reprend, et progresse jusqu'à `max_iterations` sans supervision.
Réglages : `quota_reset_tz`, `cooldown_fallback_seconds`, `cooldown_max_seconds`,
`daemon_sleep_chunk_seconds`.

---

## [2026-07-22] Calibration : arrêt propre à l'épuisement du quota

La boucle de calibration de prompt peut désormais s'arrêter proprement quand le quota
journalier du provider d'éval est épuisé, au lieu de marteler l'API en boucle sur des
coalitions vouées à l'échec. Un coupe-circuit compte les échecs de lot **consécutifs**
(paramètre `eval_max_consecutive_errors`, défaut 3) : tout succès remet le compteur à
zéro, donc une coupure réseau transitoire isolée ne l'arrête pas — seule une salve
franche (quota mort) le fait. À l'arrêt, le cache est intact : relancer le run reprend
exactement à la première coalition non payée.

**Avant :** quota épuisé → le run continuait des heures, chaque coalition rejouant 5
retries × N lots en pure perte, jusqu'au `Ctrl-C` manuel (trace Python en prime).
**Après :** au 3ᵉ échec consécutif, message `🛑 … quota probablement épuisé`, arrêt
propre sans trace, reprise gratuite au run suivant. `eval_max_consecutive_errors: 0`
rétablit l'ancien comportement.

---

## [2026-07-21] Quotas Gemma corrigés : +90 % de budget journalier, TPM enfin borné

Les deux providers Gemma (`google_gemma42` / `google_gemma43`) étaient déclarés avec des quotas
free tier erronés. Relevé sur le dashboard AI Studio, le réel est **RPM 30 · TPM 16 000 · RPD
14 400** par modèle — la config annonçait `rpm 15`, `tpm null` (« illimité ») et `rpd 1500`.

Deux effets concrets :
- **Budget journalier** : chaque Gemma passe de 1 500 à 14 400 requêtes/jour. À eux deux ils offrent
  désormais ~28 800 req/j, de loin le plus gros pourvoyeur free tier (vs 500/j pour gemini-3.1-flash-lite).
- **Anti-saturation** : le TPM était déclaré illimité, donc le load-balancer envoyait de gros batchs
  aux Gemma alors qu'ils plafonnent à 16 000 tokens/min (≈ 5 agents de 3k tokens). Le TPM réel est
  maintenant renseigné : les batchs s'auto-dimensionnent et un `max_tokens_per_request` évite les
  HTTP 413. Le `weight` tombe de 1.0 à 0.36 (les Gemma sont bornés par le TPM, comme Groq).

**Avant :** Gemma bridés à 1 500 req/j et réputés à TPM illimité → budget gâché + risque de saturation.
**Après :** Gemma exploités à 14 400 req/j chacun, débit tokens correctement borné.

---

## [2026-07-22] Calibration : poids du composite auditables (sensibilité, zéro LLM)

Les poids du composite étaient posés à la main (`global 1.0, âge 0.5, genre 0.3…`) et
mélangeaient l'**échelle** d'un terme (une L1 sur 15 tranches d'âge et une JSD n'ont pas
la même magnitude) et son **importance**. Deux ajouts, sans aucun appel modèle :

- Les losses acceptent désormais des **poids par instance** (`weights=`) ; le composite
  reste linéaire (Shapley/backtest inchangés).
- Nouvelle commande **`calibrate weights`** : reclasse les prompts déjà évalués sous
  plusieurs schémas de pondération — `uniform`, `informativity` (dérivés du pouvoir
  discriminant de chaque axe dans EMC²), `scaled` (**normalisation d'échelle** par le
  prompt seed), `strat_x2` / `strat_half` — et dit si le **meilleur prompt reste le
  meilleur** (stabilité + corrélation de rang). Répond de façon chiffrée à « pourquoi
  0.3 pour le genre ? ».

**Avant :** impossible de savoir si le classement des prompts tenait aux poids choisis.
**Après :** `calibrate weights` le vérifie en une commande, sur les décisions déjà
stockées (zéro token). *(Sur la campagne actuelle : classement STABLE, corrélations de
rang 0.96–1.0 — le gagnant ne dépend pas de la pondération.)*

---

## [2026-07-21] Calibration : mise en page du message de mutation resserrée

Le message envoyé au modèle de mutation est réordonné pour coller à sa lecture naturelle :
- La **Mémoire des leçons** passe **après** l'« Historique des mutations » (en-tête renommé
  « Historique des mutations et enseignements »), dont elle est le prolongement — au lieu d'être
  intercalée avant.
- Le rappel `💡 Opérateur à privilégier ce tour` **clôt** désormais le message (juste après la
  consigne JSON), au lieu d'être noyé entre le prompt complet et l'instruction.
- La section « ⚖️ Diversité des cibles » est **supprimée** : le garde-fou anti-resoumission
  (tabu + prescreen) empêche déjà de re-toucher trivialement le même bloc, la consigne faisait
  doublon.

**Avant :** leçons avant l'historique, rappel d'opérateur au milieu du message, section diversité
en plus.
**Après :** historique → enseignements, prompt complet, instruction, puis opérateur suggéré en
dernière ligne ; message plus court et plus lisible.

---

## [2026-07-21] Calibration : liste des opérateurs et coût-mot rappelés dans la consigne de mutation

La consigne finale envoyée au modèle de mutation (`build_mutation_user_msg`) rappelle désormais
explicitement, juste avant le JSON attendu : (1) les **7 actions possibles** (`modify`, `delete`,
`insert`, `condense`, `reorder`, `merge_blocks`, `split`) avec un résumé d'une ligne chacune ;
(2) le **coût de longueur** — chaque mot du prompt ajoute 0.05 pt d'écart (`length_penalty`), donc
à effet égal la formulation la plus courte est préférée. Vaut pour les deux chemins (candidat
unique et multi-candidats).

**Avant :** la palette d'opérateurs n'apparaissait que dans le prompt système ; la consigne finale
ne mentionnait que « modify » (l'exemple de JSON), et l'incitation à la concision n'était pas rappelée
au moment de proposer.
**Après :** le mutateur voit la liste complète des actions et le coût-mot à l'endroit où il rédige sa
proposition — il exploite mieux `condense`/`delete`/`merge_blocks` et raccourcit à effet égal.

---

## [2026-07-21] Calibration : `emd_jsd` devient la loss par défaut

La métrique par défaut d'une campagne de calibration est désormais `emd_jsd` (EMD ordinal
sur âge/distance + JSD nominal sur global/occupation/genre/motif + pondération continue par
effectif), y compris quand aucun `loss` n'est précisé. Tous les fichiers de config
l'utilisaient déjà ; seul le défaut codé dans `RunConfig` restait sur l'ancienne `l1_composite`.

**Avant :** une campagne lancée sans `loss` explicite tombait sur `l1_composite` (toutes les
catégories traitées comme interchangeables — un glissement d'âge adjacent coûtait autant qu'un
glissement lointain).
**Après :** défaut `emd_jsd`, qui respecte l'ordre des dimensions ordinales. `l1_composite`
reste sélectionnable et recalculable rétroactivement en backtest.

---

## [2026-07-21] Calibration : contexte du mutateur refondu (« ingénieur prompt »)

Le message envoyé au modèle de mutation (calibration du prompt) a été réécrit pour aller à
l'essentiel, parler d'**écart** (et non de « score composite »), et présenter le prompt de
façon plus lisible :

- **Phrase d'intro** : le message s'ouvre sur la mission (« Tu es ingénieur prompt : ta mission
  est d'optimiser le prompt système ci-dessous… »).
- En-tête `Distribution LLM actuelle :` **sans** le compte de décisions.
- **Hard negatives supprimés** (exemples individuels persona → mode) et bloc **« DEUX leviers
  prioritaires » supprimé** : redondants avec les « pires écarts strate × mode », désormais en
  **top 10** (au lieu de 6) et **sans** l'effectif `n=`.
- Ligne `Score composite actuel` retirée ; partout on parle d'**écart**. L'historique affiche
  `écart total=… (par dimension : global …, âge …, occupation …, …)`, **en toutes lettres**.
- **Historique** borné aux **5 dernières** tentatives.
- **Mémoire de leçons** : jusqu'aux **5 dernières** synthèses de rejet (au lieu d'une seule),
  numérotées.
- **Présentation unifiée du prompt** : chaque bloc est donné **dans l'ordre**, avec son **contenu
  entier** et sa contribution (Δ écart, dimensions aidées/dégradées, effet sur les modes) **sans
  abréviations**, **blocs fixes inclus**. Cette vue remplace l'ancienne table + le dump séparé des
  blocs modifiables.
- Le rappel d'opérateur ne suggère « garde de la diversité » qu'en **multi-candidats**.

**Before :** contexte long et abrégé (compte de décisions, deux leviers, hard negatives, score
composite, table markdown + dump des blocs, abréviations `g/ag/oc`, `voit`, une seule leçon).
**After :** contexte focalisé et lisible (top 10 sans effectif, 5 tentatives, 5 leçons, prompt
présenté bloc par bloc en toutes lettres avec sa contribution), plus clair pour le mutateur.

---

## [2026-07-21] Sources réorganisées en trois dépôts git + calibration en dépôt autonome

Le code est désormais réparti en **trois dépôts git** aux responsabilités claires :

- **`llm-agents-gama`** — le projet principal (pipeline LLM, GAMA, docker, docs).
- **`prompt_calibration`** — l'outil de calibration de prompt, extrait dans son propre
  dépôt (`github.com/Ytlse/prompt_calibration`), cloné à la racine sous
  `prompt_calibration/` (auparavant `scripts/prompt_calibration/`).
- **`eqasim-llm-toulouse`** — la génération de population eqasim (`eqasim-toulouse/`).

Les deux derniers sont imbriqués à la racine du projet mais **ignorés** par le dépôt
principal (comme `eqasim-toulouse/` l'était déjà). Tous les liens vers l'ancien chemin
`scripts/prompt_calibration/` ont été réparés : montage Docker, endpoint `/calibrate`,
skill `prompt_calib_context`, doc d'architecture, scripts de déploiement cloud, et le
`Makefile`/configs internes du dépôt de calibration (venv, jeux gelés, ressources
partagées). La suite de tests de calibration (209 tests) repasse au vert.

**Before :** la calibration vivait dans `scripts/prompt_calibration/` ; après son
déplacement, le lancement depuis l'IHM GAMA (`POST /calibrate`) et `make test` étaient
cassés (chemins morts, venv introuvable, imports périmés).
**After :** `prompt_calibration/` est un dépôt autonome monté dans le conteneur
`controller` sous `/app/prompt_calibration` ; `/calibrate` et `make test` fonctionnent.

---

## [2026-07-20] Calibration : Shapley 6× moins cher (jeu screen restauré) + console lisible

Trois corrections issues du diagnostic d'une campagne réelle :

- **Jeu `screen` ajouté aux jeux gelés v1** : gelés avant la phase 4, ils n'avaient
  pas le sous-échantillon de screening — Shapley et le screening se repliaient **en
  silence** sur le train complet (99 lots ≈ 100 requêtes par coalition). Le jeu
  (83 personas, filtre déterministe `in_screen` sur le train gelé — identique à ce
  que le générateur aurait produit) ramène chaque coalition à ~17 lots : **~6× moins
  de requêtes**, ~25-30 coalitions/jour sous quota gratuit au lieu de ~5.
- **Alarme sur le repli** : si le jeu `screen` manque, le lancement affiche désormais
  `[ALARME]` avec le surcoût et le remède, au lieu de dégrader silencieusement.
- **Console désambiguïsée** : le libellé Shapley porte le hash de la coalition
  (`shapley[2b:0640c803]`) — deux coalitions de même taille ne se confondent plus ;
  chaque coalition déjà payée affiche `✓ cache : …` à la reprise, et chaque passe se
  conclut par un bilan `N payée(s), M servie(s) par le cache`.

**Avant :** à la reprise, impossible de distinguer un recalcul payant d'un cache hit ;
Shapley consommait ~100 requêtes par coalition sans signal.
**Après :** la console montre ce qui est resservi gratuitement, et Shapley tourne sur
le jeu de screening prévu par l'architecture.

---

## [2026-07-20] Calibration : Shapley cumulatif à graine fixe — mêmes tokens, plus de précision

Le recalcul Shapley après chaque mutation acceptée re-tirait des permutations
aléatoires neuves : la plupart des coalitions évaluées ne retombaient jamais sur le
cache, et chaque passe repayait des évaluations qui n'apportaient pas d'information
nouvelle. Nouveau régime **cumulatif** (activé dans les configs de campagne) :

- **Socle à graine fixe** : les mêmes permutations sont rejouées à chaque passe.
  Après une réécriture de bloc, toutes les coalitions sans ce bloc sont servies par
  le cache (zéro appel LLM) — on ne paie que ce qui contient du contenu nouveau.
- **Addon plafonné** : quelques permutations fraîches s'ajoutent à chaque mutation
  acceptée (`shapley_addon_per_accept`, plafond `shapley_max_permutations`) — la
  précision de l'attribution de crédit augmente au fil de la campagne, au moment où
  les décisions (compaction, publication) en dépendent le plus.
- **Plafond ajustable en cours de campagne** : modifier le YAML suffit, pris en
  compte à la reprise suivante sans invalider le moindre calcul déjà payé.

**Avant :** chaque recalcul Shapley repayait ~toutes ses coalitions ; précision constante.
**Après :** un recalcul après réécriture ne paie que les coalitions touchant le bloc
modifié ; la précision croît (25 → 50 permutations) pour un coût par passe borné.

L'ancien comportement reste disponible (`shapley_addon_per_accept: 0`).

---

## [2026-07-17] Calibration : lancement sur une VM Google gratuite (guide clé en main)

La campagne de calibration de prompt peut désormais tourner **toute seule sur une machine
Google Cloud gratuite** (offre « Always Free » `e2-micro`), sans quitter le poste des yeux.
Un dossier `scripts/prompt_calibration/cloud/` fournit tout le nécessaire :

- **`README_CLOUD.md`** — un guide pas à pas « pour les nuls » (création de la VM, upload
  des données, clé API, automatisation), pensé pour quelqu'un qui n'a jamais touché à
  Google Cloud.
- **`config/cloud.yaml`** — la configuration de campagne côté cloud (chemins relatifs du
  dépôt, quota free tier Gemini).
- **`setup_vm.sh`** / **`run_daily.sh`** — installation en une commande, puis un réveil
  `cron` quotidien qui reprend la campagne là où le quota du jour l'avait arrêtée.
- **`data_to_upload.tar.gz`** — les jeux gelés `v1` (hors Git) prêts à envoyer à la VM.

**Coût : 0 €.** La campagne s'étale sur plusieurs jours (500 requêtes Gemini/jour en
gratuit), mais la reprise du store SQLite fait qu'il n'y a rien à surveiller : elle avance
un peu chaque nuit jusqu'à la fin.

**Avant :** la calibration ne se lançait qu'en local (poste de dev) ou via l'IHM GAMA.
**Après :** un déploiement cloud gratuit, autonome et reprenable, documenté de bout en bout.

---

## [2026-07-17] Calibration : le mutateur voit du concret (matrice bloc × mode, exemples réels, snippets entiers)

Le mutateur de prompt ne raisonnait que sur des agrégats (distributions, écarts,
contributions par dimension). Trois évolutions lui donnent du concret — **sans aucun
appel LLM supplémentaire** (données déjà persistées, uniquement calcul et formatage) :

- **Matrice bloc × mode** : la table de contribution gagne une colonne « modes poussés »
  (ex. `vélo+4 voit-3`) — l'effet de la présence de chaque bloc sur les parts modales,
  décomposé par Shapley sur les mêmes évals. Le mutateur sait *quel mode* un bloc favorise
  ou freine, au lieu de deviner la corrélation depuis les dimensions.
- **Exemples réels de décisions à corriger** (hard negatives) : jusqu'à 4 décisions
  individuelles du prompt courant (persona → mode choisi) issues des pires strates
  sur-représentées, ex. `Femme, 30 ans, actif, travail, 1-2km → voiture (+70 pts vs cible)`.
  Réglable via `hard_negatives_k` (0 → désactivé).
- **Bibliothèque d'arguments fournie en entier** : les snippets n'étaient montrés que sur
  110 caractères — tronqués en plein argument, le mutateur devait halluciner la fin.
  Contenu complet désormais (cap de sécurité à 300).

**Avant :** le mutateur devinait la relation bloc → mode et n'avait jamais vu une erreur concrète.
**Après :** chaque tour montre qui pousse quoi, et à quoi ressemble une décision aberrante type.

---

## [2026-07-17] Calibration : attribution Shapley globale à chaque acceptation (fin du leave-one-out)

La contribution de chaque bloc au score est désormais **recalculée par attribution de
crédit Shapley après *chaque* mutation acceptée** (et à l'initialisation), sur le jeu de
screening. L'ancienne ablation *leave-one-out* (retrait d'un bloc à la fois) est
entièrement supprimée : elle supposait les blocs indépendants et se trompait sur les
blocs **redondants** (jugés inutiles à tort) et **synergiques** (crédit compté deux
fois). Shapley répartit exactement le gain entre les blocs, ces deux cas compris.

**Avant :** ablation locale rapide (leave-one-out) du seul bloc touché après chaque
acceptation, et recalcul Shapley global seulement toutes les 5 acceptations — la carte
de contribution montrée au mutateur pouvait être partiellement périmée entre deux
recalculs globaux.
**Après :** carte de contribution Shapley **complète et à jour à chaque acceptation**.
Le coût reste maîtrisé : le cache adressé par contenu du store rend gratuites les
coalitions déjà évaluées (entre permutations, entre acceptations, entre runs).

Options de configuration retirées : `shapley_enabled`, `shapley_every`,
`global_ablation_every` (le comportement est désormais unique). `shapley_permutations`
(=25) et `shapley_truncation_tol` (=0.5) restent réglables.

---

## [2026-07-17] Calibration : le mutateur apprend de ses rejets (mémoire de leçons)

Le mutateur de prompt **synthétise désormais les raisons récurrentes de ses rejets**
avant de proposer, et cette synthèse est mémorisée puis réinjectée au tour suivant.
Objectif : rompre la boucle où le mutateur re-cible sans fin le même bloc parce que le
contexte affiché ne bougeait pas entre deux rejets.

Chaque rejet de l'historique est aussi **étiqueté par catégorie** : `[fond]` (une vraie
leçon existe — ne pas y retourner) vs `[bruit]`/`[seuil]`/`[doublon]` (l'idée n'est pas
invalidée, juste non significative — la reformuler). Ce garde-fou évite que le mutateur
abandonne à tort une piste correcte rejetée pour simple non-significativité statistique.

**Avant :** les causes brutes (`Δ=+0.30@n=25`, `motif +12`) étaient affichées mais jamais
généralisées ni distinguées ; le mutateur re-proposait souvent des variantes déjà écartées.
**Après :** une mémoire de leçons roulante (bornée, persistée, reprise gratuite) guide chaque
proposition vers un changement réellement distinct, en tenant compte de la nature du rejet.

La synthèse est produite dans le même appel que la proposition (coût quasi nul, aucun appel
LLM supplémentaire). Réglable via `reflection_enabled` / `lessons_max_chars` (désactivable
pour comparaison A/B).

**Garde-fou dur associé** : « ne resoumets jamais le même texte ni une variante triviale »
n'est plus qu'une consigne — c'est appliqué en code **quelle que soit la config**. Une
proposition sans changement réel, ou quasi identique à un rejet récent, est écartée **sans
aucune éval** (dans le chemin single-candidat par défaut comme dans l'entonnoir). Une
ré-soumission triviale redevient permise une fois le contexte changé (tenure du tabu).

---

## [2026-07-17] Calibration : évaluation des itinéraires sur Gemini

La campagne de calibration (`run.yaml`) évalue désormais les itinéraires avec
**Gemini** (`google_gemini31` / `gemini-3.1-flash-lite-preview`) au lieu de Mistral.
Le prompt calibré sera donc spécifique à Gemini — le modèle réellement servi en
production pour la décision d'itinéraire.

**Avant :** éval sur `mistral-small-latest`, mutations sur Gemini.
**Après :** éval **et** mutations sur Gemini `gemini-3.1-flash-lite-preview`.

⚠ Éval et mutation partagent maintenant le même quota provider Gemini. Si ce quota
devient contraignant, basculer `mutation_model` sur un autre modèle (ex.
`google_gemma42`) rétablit la séparation.

> Reprendre une campagne existante depuis un store calibré sur Mistral n'est pas
> valide (le cache d'éval Mistral ne s'applique pas à Gemini) : repartir d'un store
> neuf. `run2.yaml` reste volontairement sur Mistral pour comparaison.

---

## [2026-07-17] Calibration : retour à un essai unique avec paliers 25/50/75 %

La calibration de prompt (`scripts/prompt_calibration/`) évalue de nouveau **un seul
essai par itération** au lieu de quatre candidats en parallèle. Cet unique essai passe
par des **paliers progressifs à 25 %, 50 % puis 75 %** du jeu d'entraînement : dès qu'un
palier **n'améliore pas** le composite du prompt courant sur le même sous-échantillon,
l'essai est **abandonné immédiatement** (verdict `rejected_race`), sans jamais payer
l'évaluation complète ni les paliers suivants.

**Avant :** 4 candidats proposés par appel de mutation, départagés par racing/screening,
le meilleur passant l'éval complète.
**Après :** 1 candidat, filtré par arrêt précoce à 25/50/75 % — moins d'appels LLM
gaspillés sur des essais non prometteurs, trajectoire plus simple à suivre.

Nouveaux défauts : `n_candidates: 1`, `racing_enabled: true`,
`racing_rungs: [0.25, 0.50, 0.75]`. Le racing multi-candidats (gate de strate +
successive halving) reste disponible en remontant `n_candidates`.

---

## [2026-07-16] Calibration : racing ciblé par strate (successive halving)

Nouvelle stratégie de sélection des candidats dans l'entonnoir de
`scripts/prompt_calibration/`, **désactivée par défaut** (`racing_enabled: false`).
Elle remplace le *screening one-shot* — une seule mesure bruitée, jugée sur le
composite global — par un **racing multi-tours** précédé d'un **gate de strate**.

- **Gate strate.** Une itération sur `racing_target_every`, les candidats sont d'abord
  évalués **uniquement** sur la strate la plus mal représentée (ex. `genre[femme]`) ;
  ceux qui n'améliorent pas son écart sont éliminés d'emblée (`rejected_gate`). Si la
  strate est trop petite ou si le gate vide la liste, **repli global** — l'itération
  n'est jamais bloquée.
- **Successive halving.** Les survivants passent des paliers de train **croissants**
  (`racing_rungs`, ex. 15 % → 35 % → 70 % → 100 %) ; à chaque palier on ne garde que la
  meilleure moitié. Le budget d'éval se concentre sur les candidats qui tiennent.
- **Garde-fou statistique.** On ne départage jamais deux candidats trop proches
  (`racing_min_gap`) ou dont l'IC bootstrap chevauche — évite d'éliminer par malchance
  un candidat qui aurait gagné sur le train complet (`rejected_race` sinon).
- **Cache respecté.** Chaque palier passe par le store content-addressed ; seule la
  fraction complète réutilise le label `train`, donc l'éval complète du gagnant est
  servie par le cache quand la boucle la refait — le racing ne « repaie » pas l'historique.

**Avant :** un seul tirage de screening (~20 % du train) sur le composite global
désigne le gagnant ; les strates en échec ne sont jamais ciblées.
**Après (opt-in) :** budget concentré sur les candidats prometteurs et sur la pire
strate ; verdicts `rejected_gate` / `rejected_race` visibles au dashboard.

---

## [2026-07-16] Calibration : contexte mutateur plus lisible + diversité des blocs ciblés

Quatre améliorations du contexte fourni au mutateur de `scripts/prompt_calibration/`,
suite à une revue du rapport de mutation.

- **Légende unique dans le prompt système.** Les abréviations des dimensions
  (`ag=âge`, `oc=occupation`…) et les **conventions de signe** sont désormais
  définies une seule fois dans le prompt système du mutateur (`LEGEND_AND_SIGNS`),
  au lieu d'apparaître de façon conditionnelle et dispersée dans chaque section.
- **Signes explicités, en termes d'écart.** Le composite est une **perte à
  minimiser** ; un **Δ>0 = bloc utile**. Dans les colonnes, « + » = le bloc
  **rapproche de la cible EMC²** (réduit l'écart), « − » = il **creuse l'écart** —
  même orientation que Δ tot.
- **Table de contribution bloc × dimension, autoportante.** L'« analyse d'ablation »
  en crochets compacts est remplacée par une **table markdown** (`format_contrib_table`) :
  une ligne par bloc, une colonne par dimension (en-têtes explicites « nom (abrév) »,
  ex. `occupation (oc)`), + Δ total, triée par utilité. Une **légende de lecture des
  signes** est imprimée juste au-dessus de la table (dans le message utilisateur, pas
  seulement dans le prompt système) → lisible sans avoir à remonter à la légende
  globale. Le diagnostic textuel n'est conservé que pour les blocs nuisibles (canal mode).
- **Diversité des blocs ciblés.** Le mutateur avait tendance à toujours retoucher le
  même bloc (souvent le premier bullet). Le prompt rappelle maintenant les blocs
  récemment modifiés (`_recent_blocks`) et exige, en multi-candidats, un **bloc-cible
  distinct** par candidat ; l'entonnoir écarte sans éval les doublons de bloc (nouveau
  verdict `rejected_dup_block`), un `insert` restant distinct d'un `modify` du même ancrage.

Tests : 189 verts (`calibration/tests/`). La piste plus ambitieuse (racing ciblé par
strate + successive halving) est spécifiée dans `docs/racing-cible-strate.md`, à
implémenter ultérieurement.

**Avant :** légende parfois absente, signes ambigus, contribution en crochets denses,
mutations concentrées sur un seul bloc.
**Après :** légende + conventions de signe systématiques, table lisible, recherche
répartie sur des blocs variés.

---

## [2026-07-16] Makefile calibration : lancer un essai et l'interface en une commande

`scripts/prompt_calibration/` dispose désormais d'un Makefile. `make run essai3`
lance (ou relance/reprend au point d'arrêt) l'essai 3 dans sa propre branche isolée
du store, et `make ui` ouvre le dashboard Streamlit. Autres raccourcis : `status`,
`export`, `finalize`, `backtest`, `datasets`, `test`. Plusieurs essais peuvent
évoluer en parallèle sans se marcher dessus.

**Avant :** il fallait retenir et taper la ligne complète `../../llm-agents/.venv/bin/python
-m calibration.cli run --config … --branch …`
**Après :** `make run essai3` / `make ui` — la branche et la config (`runN.yaml`,
sinon `run.yaml`) sont résolues automatiquement à partir du nom d'essai

---

## [2026-07-16] Dashboard calibration : filtre d'expérience global et persistant

Le dashboard de calibration gagne un filtre **Expérience** unique dans la barre
latérale (menu de gauche) : on choisit une branche/îlot (ou « Toutes les branches »)
et **toutes les vues** s'y restreignent d'un coup — Timeline, DAG, Distribution,
Comparaison, Pareto, Run et Maintenance. Surtout, la sélection **reste en place quand
on change de page** : plus besoin de refiltrer à chaque vue.

**Avant :** le filtre de branche était local à la vue Timeline et repartait sur
« toutes les branches » à chaque changement de page ; les autres vues n'avaient aucun
filtre d'expérience
**Après :** un filtre unique en barre latérale, appliqué à toutes les vues et
mémorisé d'une page à l'autre

---

## [2026-07-15] Dashboard calibration : vue Comparaison vs vérité terrain + carte d'ablation détaillée

Le dashboard de calibration gagne une vue **Comparaison** : des graphiques en barres
confrontent les parts modales de plusieurs prompts (par défaut le prompt de départ et
le meilleur trouvé) à la **vérité terrain EMC²**, en global ou strate par strate
(âge, occupation, genre, motif, distance — un graphique par catégorie, avec les
effectifs). On voit d'un coup d'œil où un prompt calibré colle à l'enquête et où il
dévie encore, sans aucun réappel LLM (tout est reconstruit des décisions stockées).

La carte d'ablation de la vue DAG affiche désormais le **détail par dimension** de
chaque bloc (une colonne par dimension, dégradé vert/rouge), avec un garde-fou : un
détail incohérent avec le Δ du bloc (évals legacy partielles) est masqué plutôt
qu'affiché faux.

**Avant :** la vue Distribution ne montrait qu'un seul nœud, en global uniquement ;
l'ablation n'affichait qu'un Δ par bloc
**Après :** comparaison multi-prompts vs EMC² par strate ; ablation décomposée par
dimension

Corrige au passage : sélection du nœud seed dans la vue DAG (plantait sur le parent
manquant), et choix de l'éval de référence quand un nœud porte plusieurs évals train
(les artefacts sans décisions brutes sont ignorés).

---

## [2026-07-15] Calibration : impact de chaque bloc détaillé par dimension (âge, motif, …)

La carte d'ablation/Shapley fournie au mutateur ne dit plus seulement qu'un bloc est
utile ou nuisible : elle indique **sur quelles dimensions** il agit, en points de
composite, avec une légende des abréviations. Le mutateur peut ainsi réécrire un bloc
pour conserver sa dimension forte tout en corrigeant son effet secondaire, au lieu de
choisir entre le garder et le supprimer.

Cette décomposition est **gratuite** : le score composite étant une somme pondérée des
dimensions, les mêmes évaluations de coalitions (Shapley) ou d'ablation (LOO) suffisent
— zéro appel LLM supplémentaire. Les contributions sous ±1 pt sont masquées (bruit).

**Avant :** `• bloc_meteo (Δ=+4.2) : Par beau temps, envisage la marche…`
**Après :** `• bloc_meteo (Δ=+4.2) [mo+3 ag+2 | oc-2] : Par beau temps, envisage la marche…`
(légende : g=global, ab=modes absents, ag=âge, oc=occupation, ge=genre, mo=motif,
di=distance, lg=longueur — le bloc aide motif et âge, dégrade légèrement occupation)

Le détail est persisté dans le store (`ablations.scores_json` pour les lignes
`shapley`) et la légende est aussi rappelée dans l'historique des mutations.

**Rétro-compat :** à la reprise d'une campagne lancée avant cette évolution, le
détail est reconstitué automatiquement depuis le store (zéro éval) — le mutateur
voit les crochets dès la première itération reprise. Les prompts de mutation déjà
stockés (vue Timeline) restent figés tels qu'ils ont été générés.

---

## [2026-07-15] Calibration : finalisation et publication du prompt calibré

La calibration de prompt (`scripts/prompt_calibration/`) sait désormais **conclure une
campagne en une commande** : `calibrate finalize` désigne le meilleur prompt trouvé,
mesure sa qualité sur le jeu de test réservé, et le publie.

**Le chiffre publiable.** Le meilleur prompt (toutes branches d'îlots confondues) est
évalué **une seule fois** sur le jeu `test` — un jeu gelé que la boucle d'optimisation
n'a jamais vu, donc une mesure honnête et non surajustée. Le prompt de départ est
évalué sur le même jeu pour donner une comparaison **avant/après** immédiate.

**Le bilan.** La commande imprime, pour le seed et le meilleur : le score par jeu
(entraînement / validation / test) et son évolution, le détail par dimension sur le
test, le nombre de mots du prompt (avant/après), le nombre d'évaluations LLM consommées
et la durée approximative de la campagne.

**La publication.** Par défaut la commande est un **essai à blanc** (rien n'est écrit).
Avec `--write`, le prompt calibré est ajouté à `prompts.yaml` sous une clé horodatée
`calibrated_…` (aucune entrée existante n'est modifiée) ; `--activate` le rend actif.

**Before :** conclure une campagne demandait de retrouver le meilleur prompt à la main,
de l'évaluer et de le recopier dans `prompts.yaml` — sans mesure de test standardisée.
**After :** une seule commande produit le score de test publiable, le bilan avant/après
et l'écriture (optionnelle et explicite) du prompt calibré.

---

## [2026-07-15] Calibration : îlots parallèles, merge et archive de Pareto

La calibration de prompt (`scripts/prompt_calibration/`) peut désormais explorer
**plusieurs pistes en parallèle** plutôt qu'une seule trajectoire, et capitaliser les
arguments qui marchent — ce qui augmente les chances de trouver un meilleur prompt à
budget d'évaluation comparable.

**Îlots parallèles.** `calibrate run --islands 3` fait évoluer 3 branches
indépendantes dans le même historique, chacune avec sa propre boucle reprenable. Elles
avancent à tour de rôle sous le même budget de requêtes ; toutes les quelques
itérations, le meilleur prompt d'un îlot est **proposé** (jamais imposé) à l'îlot
voisin — il n'est adopté que s'il améliore vraiment ce dernier. On évite ainsi qu'une
seule mauvaise piste condamne toute la campagne.

**Merge (crossover).** Deux prompts **complémentaires** — l'un bon sur l'âge, l'autre
sur le motif — peuvent être fusionnés par le modèle de mutation en un prompt enfant qui
combine leurs forces, puis évalué comme n'importe quel candidat (deux bons parents ne
font pas toujours un bon enfant : aucun merge n'est gardé sans mesure).

**Archive de Pareto.** Le score composite écrase six dimensions en un seul chiffre ;
deux prompts au même score peuvent en réalité être forts sur des dimensions
différentes. L'archive conserve désormais tous les prompts **non dominés** (ceux
qu'aucun autre ne bat sur toutes les dimensions à la fois) — matière première des
départs d'îlots diversifiés et des parents de merge. Une nouvelle vue **Pareto** du
dashboard la rend visible (nuage de compromis + bibliothèque d'arguments).

**Bibliothèque d'arguments.** Chaque bloc ajouté ou réécrit qui apporte un gain net est
capitalisé (taggé par le mode qu'il a aidé) et resservi au modèle de mutation comme
matière à réutiliser — les îlots se fertilisent ainsi mutuellement, et une future
campagne peut démarrer avec cette banque.

**Before :** une seule trajectoire d'optimisation ; un prompt au score équivalent mais
au profil complémentaire était perdu ; les bons arguments trouvés n'étaient pas réutilisés.
**After :** plusieurs îlots explorent en parallèle, échangent leurs meilleurs prompts et
peuvent les fusionner ; les compromis non dominés sont archivés et les arguments
gagnants capitalisés.

---

## [2026-07-14] Calibration : attribution de crédit par valeur de Shapley

La calibration de prompt (`scripts/prompt_calibration/`) mesure désormais **plus
justement** ce que chaque bloc du prompt apporte au score, ce qui oriente mieux les
mutations et les suppressions.

**Le problème de l'ancienne mesure.** Jusqu'ici, l'importance d'un bloc était estimée
en le retirant seul et en regardant la variation du score (« ablation un-bloc-à-la-fois »).
Cette mesure se trompe dès que les blocs interagissent : deux blocs qui disent la même
chose paraissent chacun **inutiles** (l'autre compense) — au risque de supprimer les
deux ; deux blocs qui n'agissent qu'**ensemble** se voient chacun attribuer tout le
mérite, gonflant artificiellement leur importance.

**La correction : la valeur de Shapley.** Chaque bloc est vu comme un « joueur » dont
la contribution est moyennée sur de nombreux ordres d'ajout possibles. Le mérite total
est ainsi réparti **exactement** entre les blocs, redondances et synergies comprises.
Le calcul reste économe : échantillonnage aléatoire tronqué (on s'arrête dès que le
prompt complet est reconstitué), mené sur un petit échantillon (~20 % des trajets), et
les combinaisons déjà évaluées sont resservies gratuitement par le cache.

**Before :** l'importance d'un bloc = effet de son retrait isolé → deux blocs
redondants semblent inutiles, deux blocs synergiques semblent tous deux indispensables.
**After :** l'importance = contribution moyenne équitable → la carte des blocs utiles /
nuisibles reflète les interactions réelles, et guide mieux réécritures et compactions.

---

## [2026-07-14] Calibration : entonnoir de mutation, opérateurs riches et compaction du prompt

La boucle de calibration de prompt (`scripts/prompt_calibration/`) dépense désormais
beaucoup moins d'évaluations LLM pour progresser davantage, et sait **raccourcir** le
prompt sans dégrader le score.

**Un entonnoir au lieu d'une mutation à l'aveugle.** À chaque tour, le modèle de
mutation propose maintenant **plusieurs pistes en un seul appel**. Elles franchissent
un entonnoir qui n'évalue au prix fort que ce qui le mérite :
- **Tabu** — une piste quasi identique à une modification déjà tentée et rejetée est
  écartée immédiatement, sans aucune évaluation. Elle redevient tentable plus tard,
  une fois que le prompt a suffisamment évolué.
- **Pré-sélection rapide** — les pistes restantes sont comparées sur un petit
  échantillon (~20 % des trajets) ; seule la meilleure passe l'évaluation complète et
  le test statistique.

**La boucle apprend quels leviers marchent.** Un bandit choisit l'opérateur à
privilégier (réécrire, supprimer, insérer, déplacer, fusionner, condenser, scinder un
bloc) en fonction de ce qui a été accepté jusqu'ici — visible au dashboard.

**Le prompt est activement raccourci.** Périodiquement et en fin de campagne, une passe
de **compaction** retire les blocs qui n'apportent rien, à condition de prouver
statistiquement que le score ne se dégrade pas. Comme le prompt calibré est envoyé à
chaque décision d'itinéraire en production, chaque mot économisé est payé des millions
de fois.

**Before :** chaque itération = une mutation évaluée sur tout le train, prompt qui ne
fait que grossir.
**After :** plusieurs candidats filtrés à bas coût par tour, opérateurs arbitrés
automatiquement, et un prompt qui se raccourcit tant que le score tient.

---

## [2026-07-14] Calibration : loss ordinale (EMD/JSD) et acceptation statistique

La calibration de prompt (`scripts/prompt_calibration/`) mesure et accepte désormais
plus juste.

**Loss v2 (`emd_jsd`, au choix via `loss:` dans la config).** L'ancienne loss L1
traitait toutes les tranches comme interchangeables : rendre les 15-19 ans un peu trop
adeptes du bus vers les 20-24 ans coûtait autant que vers les 50-54 ans. La nouvelle
loss respecte l'ordre des tranches — âge et distance sont mesurés par **EMD** (coût de
déplacement le long de l'axe), un décalage vers une tranche voisine coûte moins qu'un
décalage lointain. Les critères sans ordre (occupation, genre, motif, global) passent
à la **divergence de Jensen-Shannon**, et chaque strate compte désormais au prorata de
son effectif au lieu d'être ignorée sous 5 individus.

**Acceptation statistique (bootstrap).** Une mutation n'est retenue que si son gain est
**significatif** : un rééchantillonnage des agents (bootstrap apparié) estime si
l'amélioration tient au-delà du bruit d'échantillon. Le recuit assouplit l'exigence de
significativité en début de campagne (exploration) mais **jamais le signe** — une
mutation qui dégrade le score n'est plus jamais acceptée. Les rejets « pour bruit » sont
tracés (`rejected_stat`) et renvoyés au mutateur.

**Backtest sans réappel LLM.** `calibrate backtest --metrics l1_composite,emd_jsd`
recalcule n'importe quelle loss sur tout l'historique déjà stocké (les décisions brutes
sont conservées) et compare les trajectoires — on choisit la loss en connaissance de
cause avant de basculer une campagne.

**Avant :** score L1 aveugle à l'ordre des tranches ; une mutation acceptée dès que le
composite baissait, même d'un poil sous le bruit.

**Après :** l'erreur reflète la distance réelle entre tranches ; seules les
améliorations statistiquement solides sont conservées, et toute loss est rejouable
rétroactivement sur l'historique.

---

## [2026-07-13] Dashboard de calibration : l'historique d'une campagne, explorable en direct

Le moteur de calibration de prompt (`scripts/prompt_calibration/`) a désormais un
**dashboard Streamlit**, lecteur pur du store SQLite, rafraîchissable pendant qu'une
campagne tourne. On y explore toute l'histoire d'une campagne sans notebook :

- **Timeline** : chaque mutation depuis l'origine avec son verdict et son score
  composite *et* par dimension, filtrable, avec la courbe du meilleur score ;
- **DAG** : le graphe de lignée des prompts coloré par score — un clic sur un nœud
  ouvre son prompt, le diff avec son parent, ses scores et sa carte d'ablation ;
- **Distribution** : parts modales actuelles vs cible EMC² et pires croisements
  strate × mode, reconstruits depuis les décisions brutes (aucun appel LLM) ;
- **Run** : itération, meilleur score, modèles/températures, volumétrie d'éval ;
- **Maintenance** : lance les commandes `status` / `export` / `import` directement
  depuis la page — statut lisible, export téléchargeable, et import d'un ancien run
  (protégé par une confirmation, car il écrit dans l'historique).

Lancement : `calibrate dashboard --config run.yaml`. Chaque vue a son lien
partageable (`?view=DAG`). Au passage, `--config`/`--branch` s'acceptent désormais
aussi bien avant qu'après la sous-commande (`calibrate dashboard --config run.yaml`
fonctionne, avant il fallait `calibrate --config run.yaml dashboard`).

**Avant :** l'historique d'une campagne se lisait au mieux via l'export CSV/Markdown
ou en rejouant le notebook ; la progression d'un run se suivait dans les logs.

**Après :** une page web unique montre chaque mutation moins de 30 s après son
verdict et rend tout l'historique d'un run terminé explorable (timeline, DAG,
distributions) sans rien recalculer.

---

## [2026-07-13] Météo par persona : les lots LLM mélangent enfin les conditions

La météo (et le contexte trafic) est désormais **attachée à chaque persona** au lieu
d'un unique préambule commun en tête de requête. Conséquence directe : des demandes
de **météos différentes peuvent maintenant être fusionnées dans un même appel LLM**,
chaque persona gardant sa propre météo dans le prompt.

**Avant :** la météo était un paramètre de la requête ; comme le regroupement en lots
ne fusionne que des requêtes de paramètres identiques, deux agents sous des météos
différentes partaient dans des appels LLM séparés. Le micro-batching était bridé par
la météo, d'où des lots plus petits et plus d'appels.

**Après :** la météo voyage dans le bloc de l'agent. Le regroupement ne la voit plus,
donc il fusionne des agents quelle que soit leur météo ; le prompt affiche
`**Contexte :** …` sous l'en-tête de chaque persona (sa météo propre). Lots plus
pleins, moins d'appels, pour un débit et une pression de rate-limit meilleurs.

- **Décisions inchangées** : chaque persona voit exactement la même météo qu'avant,
  juste attachée à son bloc plutôt qu'en préambule — seul le **remplissage des lots**
  change.
- **Fidélité de calibration** : le pipeline de calibration applique le même format
  d'injection par persona, donc la mesure reflète le prompt réellement envoyé.

---

## [2026-07-13] Lancer la calibration du prompt depuis l'IHM GAMA

Un bouton **« Lancer la calibration du prompt »** apparaît dans l'interface GAMA
(catégorie *Calibration* des paramètres de l'expérience `e`). Il déclenche une
campagne de calibration en tâche de fond dans le contrôleur, sans quitter la
simulation ni la ligne de commande. Un paramètre **« Calibration - cycles
(itérations) »** (1–200) règle le nombre d'itérations de la boucle.

**Avant :** la calibration ne se lançait qu'en ligne de commande, depuis l'hôte
(`python -m calibration.cli run --iterations N` dans `scripts/prompt_calibration`).

**Après :** on règle le nombre de cycles dans l'IHM puis on clique sur le bouton.
GAMA envoie `POST /calibrate {iterations}` au contrôleur, qui lance la campagne en
sous-processus détaché (un seul run à la fois) et répond immédiatement. La console
GAMA affiche l'accusé de démarrage (pid, cycles, chemin du journal) ; la sortie de
la campagne est journalisée dans `experiments/current/calibration.log`.

- **Non bloquant** : la simulation continue, le contrôleur exécute la calibration
  en arrière-plan. Une seconde demande pendant qu'un run tourne est refusée
  proprement (message `calibration_busy`).
- **Prérequis** : les jeux gelés (`calibration_datasets/<version>/`) doivent exister
  et les clés API des providers être présentes dans `.env` — sinon la campagne
  s'arrête avec une erreur explicite dans `calibration.log`.

---

## [2026-07-13] Calibration de prompt : phase 1 livrée — moteur reprenable + store SQLite

Le moteur de calibration devient un **package Python testé et reprenable à tout
moment**, piloté par une CLI, avec un historique persistant interrogeable.
Fini le notebook monolithique à globals : `scripts/prompt_calibration/calibration/`
(models, blocks, metrics, evaluation, mutation, loop, store, cli) — 65 tests verts.

- **Reprise sans recalcul** : l'historique complet (prompts, mutations, évals,
  ablations) vit dans un unique store SQLite `calibration.db` où chaque prompt est
  un nœud d'un DAG identifié par le hash de son texte (comme un commit git). Tuer
  le process en pleine itération puis relancer `calibrate resume` repart
  exactement à l'itération suivante — les évals déjà calculées sont servies par le
  cache, les mutations déjà jouées rejouées à l'identique : **zéro appel LLM
  redondant**. L'init (run initial + ablation) n'est refaite que si on part de zéro.
- **Décisions brutes conservées** : chaque éval stocke ses choix modaux
  `(agent_id, mode)`, donc toute métrique future (loss v2 en phase 3) est
  recalculable rétroactivement sans réappel LLM.
- **CLI** : `calibrate run | resume | status | export | import`. `export` produit
  une vue lisible (`nodes.csv`, `mutations.csv`, `history.md`) ; `import` récupère
  les anciens runs (`mutations.jsonl` + historique) dans le nouveau store.
- **Configuration par fichier** : tout paramètre passe par un `RunConfig` (YAML),
  plus aucun global mutable.
- **Jeux val/test nettoyés de la mémoire** (fin de phase 0) : la section
  `**Historique :**` (souvenirs STM/LTM, spécifique au run source et non
  reproductible) est retirée des personas des jeux val et test à leur génération —
  la mesure de référence ne dépend plus que du profil, de la météo et des options
  de trajet. Le train la conserve (il ne sert qu'à la boucle).

**Avant :** calibration dans un notebook (état invisible, non testable) ; une
interruption imposait de relancer depuis un checkpoint approximatif ; historique
éparpillé en CSV/JSONL non reliés
**Après :** moteur importable et testé, reprise exacte au point d'arrêt via un
store SQLite, historique complet requêtable en SQL et exportable

---

## [2026-07-13] Calibration de prompt : phase 0 livrée — mesure fiabilisée

La refonte de l'outil de calibration démarre dans un nouveau package,
`scripts/prompt_calibration/` (l'ancienne version notebook est conservée intacte
dans `scripts/models_influence/`). La phase 0 du ticket 004 est livrée : la mesure
sur laquelle toute l'optimisation repose est désormais fiable.

- **Métadonnées exactes** : les attributs de scoring (genre, âge, occupation,
  taille du ménage) proviennent de la jointure `agent_id → population_N.json`,
  plus du parsing du texte. Le genre vient de `traits_json.gender` — fin de
  l'inférence par prénom et de ses erreurs connues.
- **Dérive de format résorbée** : les deux formats d'en-tête de logs
  (`--- agent_id=… ---` courant et `--- PERSONA … ---` legacy) sont parsés,
  et le journal est lu correctement même en JSON pretty-printed concaténé.
- **Jeux gelés train/val/test** : affectation stable par `sha256(agent_id)`,
  versions figées avec manifest (hash des sources, effectifs par strate) et
  rapport de couverture des marginales Cerema (strate manquante = warning).
- **Température d'évaluation minimale** (`EVAL_TEMP = 0.0`).

**Avant :** genre parfois faux (heuristique prénom), logs récents non parsables
(0 % de rattachement), jeux rééchantillonnés à chaque run
**Après :** 100 % des 720 sections de `experiments/current` rattachées à leurs
métadonnées exactes (vérifié par `check_phase0.py`), jeux reproductibles et gelés

---

## [2026-07-13] Calibration de prompt : documentation et plan d'industrialisation

Le module de calibration de prompt (`scripts/models_influence/prompt_calibration.ipynb`)
dispose désormais d'une documentation d'architecture (`docs/arch/prompt_calibration.md`)
et d'un plan de refonte en 8 phases (`docs/tickets/ticket_004_prompt_calibration_industrialisation.md`) :
mesure fiabilisée (métadonnées structurées, jeux gelés train/val/test), store SQLite
git-like reprenable, dashboard Streamlit, loss ordinale EMD/JSD, acceptation
statistique, attribution de crédit Shapley, branches parallèles avec merge,
minimisation du prompt à score constant (économie de tokens en production), et revue
de littérature scorée (GEPA, HiveMind, MAPGD, MASS, MARS, RePrompt…).

Deux anomalies documentées au passage : le genre des personas est inféré du prénom
alors qu'il existe dans `traits_json.gender` de la population générée, et le format
d'en-tête des logs récents (`--- agent_id=… ---`) ne correspond plus au regex de la
lib (`--- PERSONA … ---`) — corrections planifiées en phase 0 du ticket.

---

## [2026-07-11] Fin des HTTP 413 groq : capacité par requête vérifiée avant l'envoi

Sur le run du 2026-07-11, 38 des 63 erreurs LLM étaient des 413 « request too large »
sur les providers groq : le free tier rejette toute requête unique dont
`prompt + max_tokens` dépasse le TPM, et deux providers (`groq_openai_120/20`,
plafond 8 000) partaient sans aucun clamp — `groq_openai_120` n'a servi qu'un seul
batch sur tout le run malgré 30 RPM de quota disponible.

- Tous les providers groq déclarent désormais `max_tokens_per_request` (= leur TPM),
  qui borne aussi la taille des batchs constitués.
- Le `max_tokens` envoyé est rogné d'après la taille **réelle** du prompt rendu
  (l'estimation statique sous-évaluait les prompts de réflexion d'un facteur 2).
- Si même la sortie minimale ne tient plus, le batch est rerouté vers un autre
  modèle **avant** l'appel HTTP (nouveau compteur `llm_capacity_reroute_total`).

**Avant :** requêtes condamnées envoyées quand même — 413, retries brûlés, cascades
« providers saturés », capacité groq quasi inutilisée
**Après :** zéro 413 évitable, la capacité groq (~90 RPM cumulés) redevient
exploitable pour résorber le backlog de planification

---

## [2026-07-11] Réflexions STM ordonnancées en EDF avec garantie < 12 h simulées

Les réflexions STM partaient en fire-and-forget vers le gateway dès leur déclenchement
et se battaient avec les planifications de trajets aux heures de pointe : sur le run du
2026-07-11, 219 réflexions perdues (timeouts 120 s, providers saturés) et l'essentiel
des 411 ERROR du log. Elles passent désormais par la file EDF avec une échéance en
temps simulé de 12 h (`stm_reflection_deadline_sim_s`).

- Les planifs urgentes passent d'abord ; les réflexions remplissent les creux et
  remontent en priorité à l'approche de leur échéance.
- La contre-pression prédictive compte leurs échéances : si le débit LLM ne permet
  plus de les tenir, le `/sync` est retenu et le temps simulé se fige le temps de
  drainer — la garantie 12 h simulées est structurelle.
- Un échec gateway ne repousse pas l'échéance : la re-soumission au sync suivant
  garde la deadline d'origine, donc la priorité monte à chaque retentative.
- Nouvelle alarme `[ALARME]` (visible via `make error`) si une réflexion dépasse
  quand même son échéance simulée.

**Avant :** réflexions en concurrence frontale avec les planifs, échecs massifs
silencieusement retentés sans limite de retard
**Après :** réflexions servies dans les creux de charge, avec échéance simulée
garantie de 12 h et alarme en cas de dépassement

---

## [2026-07-11] Micro-batching réellement exploité : le ratio agents/prompt décolle

Le micro-batching regroupait très peu (2,4 agents/prompt sur le run du 2026-07-10,
57 % des prompts partaient avec un seul agent) alors que Mistral, qui porte 64 % du
trafic, plafonne à 20 agents/prompt. Quatre correctifs s'attaquent à la cause :

- **Seuil de dispatch découplé du plus petit provider** : le dispatch immédiat se
  déclenchait dès 1 tâche en file (min des providers, tiré vers 1 par les petits TPM
  Groq), court-circuitant la fenêtre d'accumulation. Le seuil est désormais une cible
  de batch (`batch_target_agents`, 10) ; en dessous, la fenêtre d'accumulation joue.
- **Fenêtre d'accumulation élargie** : 1 s → 3 s, calée sur l'inter-arrivée mesurée
  des prompts (p50 = 1,4 s).
- **Capacités de batch recalibrées sur les tokens réels** : le calcul supposait
  6 296 tokens/agent alors que le mesuré est ~1 600 ; avec 3 000 (marge 25 %), les
  providers bornés par le TPM acceptent des batchs 2 à 4× plus gros
  (groq_llama4 : 4 → 10, groq_llama3 : 1 → 4, cerebras : 4 → 5).
- **Concurrence Mistral réduite (5 → 3 workers)** : cinq workers se disputaient la
  file et la vidaient en pops d'une tâche ; moins de workers = pops plus gros, même
  débit (RPM 90 loin d'être saturé).

**Avant :** ~2,4 agents/prompt (médiane 1), batching accidentel uniquement quand le
backlog s'accumulait ; system prompt (~900 tokens) dupliqué dans chaque requête.
**Après :** les tâches compatibles s'accumulent jusqu'à 3 s ou 10 tâches avant envoi,
puis le worker remplit le batch à la capacité réelle du provider — moins de requêtes,
moins de tokens dupliqués, plus de marge RPM pour les pics (moins de 429/fallbacks).
Contrepartie : +3 s de latence max par décision, négligeable devant l'appel LLM (2-10 s).

À surveiller au prochain run : le panneau « Ratio batching (agents/prompt) » du
dashboard LLM Gateway, et les `ProviderParseError` sur les gros batchs (un batch
de 20 en échec = 20 agents à rejouer).

---

## [2026-07-11] Limitation documentée : cache OTP raté d'un jour simulé à l'autre

La clé du cache OTP persistant inclut la date simulée absolue, calculée avant le
remapping `gtfs.fixed_day`. Conséquence : même avec `fixed_day` actif (requêtes OTP
identiques d'un jour à l'autre), un cache réchauffé au jour J est intégralement raté
au jour J+1. La limitation est maintenant documentée dans `docs/arch/cache-memory.md`
et un TODO est posé dans `OtpPersistentCache.make_key` (aligner la partie date de la
clé sur la date fixe ou le jour de semaine, comme le cache OSMnx). Aucun changement
de comportement pour l'instant.

---

## [2026-07-10] Dashboard Métier Mobilité : ponctualité des départs

Nouvelle row « Ponctualité des départs (phase live) » dans le dashboard
« 07 · Métier Mobilité » : elle répond d'un coup d'œil à « les agents
partent-ils à l'heure ? » :

- **Départs à l'heure** vs **en retard** (seuil : action poussée vers GAMA
  plus de 60 s après l'heure prévue), avec le **% de départs à l'heure** ;
- pour les retardataires : **retard moyen** et **retard max** du run ;
- **départs ratés** : la planification (réponse LLM) est arrivée si tard que
  même l'heure d'arrivée prévue était déjà passée ;
- **sans réponse LLM** : activités parties sur l'itinéraire par défaut faute
  de réponse à temps (saturation/timeout) ;
- un graphique temporel « à l'heure / en retard / ratés » par tranche de 10 min.

Le bootstrap (/init) est exclu : il pré-calcule les itinéraires et ne mesure
pas de vrais départs.

**Before :** la ponctualité se reconstruisait après coup via `/debug-run`
(logs LATE) ; aucun indicateur live de retard moyen/max ni de départs ratés.
**After :** l'état de ponctualité des agents est visible en continu dans le
dashboard métier, seuils colorés (orange dès 10 retards ou 5 min de retard moyen).

---

## [2026-07-10] Dashboard LLM Gateway : panneaux providers lisibles et « Réactivation dans (s) » réparé

Trois lisibilités corrigées sur le dashboard « 04 · LLM Gateway » :

- **État des providers** : chaque tuile affiche maintenant le nom du provider
  au-dessus de son état (Actif, Cooldown, …) — plus besoin de deviner quelle
  tuile correspond à quel provider.
- **Réactivation dans (s)** : le panneau restait à 0 même quand un provider
  était en cooldown, car la métrique ne couvrait que la désactivation
  temporaire (erreurs consécutives), pas le cooldown 429/5xx — de loin le cas
  le plus fréquent. La métrique expose désormais le TTL restant quel que soit
  le mécanisme.
- **Tokens cumulés par provider & modèle** : les barres étaient légendées avec
  le jeu de labels Prometheus brut (`{instance=…, job=…, model=…, provider=…}`) ;
  elles affichent maintenant `provider · modèle` (ex. `google_gemini31 ·
  gemini-3.1-flash-lite-preview`).

**Before :** un provider en cooldown affichait « Réactivation dans 0 s » ;
états et tokens illisibles sans survoler chaque série.
**After :** le compte à rebours de réactivation est correct pour cooldown et
désactivation ; provider identifiable d'un coup d'œil sur les trois panneaux.

---

## [2026-07-10] Dashboard Métier Mobilité : graphiques en heure simulée

Les trois graphiques temporels du dashboard Grafana « 07 · Métier Mobilité »
(parts modales dans le temps, trajets par motif, états des agents) affichent
désormais l'**heure de la simulation** sur l'axe X, au lieu de l'heure réelle.
La lecture métier devient directe : un pic voiture à 8h correspond bien à 8h
du matin *vécu par les agents*, quelle que soit la vitesse d'exécution du run.

**Before :** l'axe X montrait l'heure réelle du poste ; avec une simulation
accélérée (ou ralentie par le backpressure), impossible de relier un pic modal
à un moment de la journée simulée.
**After :** l'axe X suit `gama_sim_logical_time_seconds` — les courbes se lisent
en heures de la journée simulée. La plage temporelle sélectionnée en haut de
Grafana reste en temps réel ; restreindre la plage au run courant si plusieurs
runs sont couverts (l'axe repartirait en arrière à chaque /init).

---

## [2026-07-10] Répartition LLM proportionnelle à la capacité réelle et réservation TPM à la taille exacte

Le load balancer distribue désormais les requêtes proportionnellement à la capacité
**effective** de chaque provider (`min(RPM, TPM/3000)`), et la fenêtre TPM glissante est
recalée sur la taille réelle de chaque requête (prompt mesuré en caractères / 3, puis
tokens facturés) au lieu d'un forfait fixe de 3 000 tokens.

Ce que ça débloque :
- **Les gros providers absorbent enfin leur part** : mistral passe de ~8 % à ~49 % de la
  rotation (il détient 47 % de la capacité totale) ; la flotte Groq bridée à 6-12k TPM
  descend à 1-2 % chacun au lieu de saturer.
- **Fin du sous-comptage des grosses requêtes** : une réflexion STM (~4 500 tokens_in/agent,
  2× le forfait) réserve son vrai coût — c'est ce sous-comptage qui produisait des
  violations TPM (groq_qwen mesuré à 122 % de son quota) et des 429.
- **Les petites requêtes rendent leur headroom** : un batch plus léger que le forfait
  libère immédiatement la différence pour les autres workers.
- Un WARNING signale toute requête dont le coût réel dépasse l'estimation de +25 %
  (dérive du ratio caractères/tokens, mesuré à 3,05-3,50 sur run réel).

**Before :** mistral utilisé à 7 %, groq_qwen à 122 % de son TPM, 29 % des minutes actives
avec des 429, réflexions STM abandonnées en masse (« providers saturés »).
**After :** rotation alignée sur les quotas ; la fenêtre TPM reflète la consommation réelle
requête par requête.

---

## [2026-07-10] Réduction des fallbacks LLM : throttling de concurrence et timeouts étendus

Baisse drastique du fallback LLM (6.8% → ~0%) via throttling de la concurrence et tolérance accrue aux 5xx.

**Changes :**
- `worker_concurrency`: 20 → 8 (60% moins de requêtes parallèles, réduit la saturation des providers)
- `remote_llm_poll_timeout`: 60s → 120s (double du temps d'attente avant fallback, absorbe cooldowns 5xx)
- Google Gemma 42/43: `concurrency_limit` réduit à 1, `disable_timeout` augmenté à 180s (plus patient après erreur)

**Before :** 254/3753 trajets (6.8%) en fallback, backlog p95 = 963s, 9 rate-limits 429, Google 500 systématiques.
**After :** Pipeline moins saturé, providers moins overwhelmés, meilleure absorption des cooldowns transitoires.

---

## [2026-07-10] Refonte des dashboards Grafana : 8 vues par question, alertes et alarmes visibles

Les 5 dashboards historiques (cockpit, bottleneck, llm_agents, business, system) sont remplacés
par 8 dashboards numérotés par cycle de vie — `01_cockpit` (le run va-t-il bien ?),
`02_init_bootstrap`, `03_pipeline_scheduling`, `04_llm_gateway`, `05_routing`, `06_cache_llm`,
`07_metier_mobilite`, `08_systeme` — reliés par un menu déroulant commun. Le live ne garde que
les indicateurs actionnables pendant le run ; l'analyse fine reste dans `/debug-run`.

Ce que la refonte débloque :
- **Les alarmes `[ALARME]` sont enfin visibles dans Grafana** (compteur `alarme_total{source}`,
  feu « santé globale » dans le cockpit) et **7 alertes Grafana provisionnées** couvrent les cas
  critiques (agents bloqués, fallback LLM >10 %, aucun provider actif, drainage prolongé…).
- **La couverture du cache Qdrant** (`llm_cache_points_*`, agents couverts) répond en un coup
  d'œil à « le cache est-il assez peuplé pour l'init ? » (dashboard 02).
- **Le coût est suivi en tokens** : tokens/heure simulée, tokens économisés par le cache (04, 06).
- **Nouvelle lecture métier** : parts modales dans le temps, mode × motif d'activité
  (`trip_mode_by_purpose_total`, couvre LLM + cache + mono-choix), les 7 tranches de distance
  (les trajets 10-20 km et 20-50 km étaient invisibles), palette officielle des modes appliquée.
- **CPU/RAM par conteneur** via cAdvisor (dashboard 08) — on voit désormais *qui* consomme.
- **Toutes les vagues du bootstrap sont visibles** (`agent_bootstrap_wave_moves{wave,status}`,
  dashboard 02) : 8 lignes, une par vague, chacune avec progression, agents traités/obtenus/
  planifiés et cache hit % — seule la vague 1 était détaillée auparavant.
- Panneaux cassés corrigés : PromQL invalide sur les tokens par modèle, latence OTP par instance
  (label `instance` → `otp_instance`, il était écrasé par Prometheus), famille EDF/backpressure
  et OSMnx (ok/err/latence) enfin affichées.

**Before :** 5 dashboards accumulés, panels vides (PromQL invalide), alarmes visibles uniquement
via `make error`, tranches 10-50 km absentes, aucun coût en tokens ni vue par conteneur.
**After :** 8 dashboards par question, alertes provisionnées, feu santé + compteur d'alarmes,
coût en tokens, couverture cache Qdrant, mode × motif, CPU/RAM par conteneur.

`/debug-run` affiche en plus le ratio de choix d'itinéraire par défaut rapporté aux seules
décisions LLM (erreur définitive), avec alarme au-delà du seuil. Les métriques SDK dupliquées
(`llm_tasks_*`, `llm_mode_chosen_total`, `llm_index_chosen_total`) sont supprimées ; la latence
`/sync` est mesurée (`controller_sync_duration_seconds`).

---

## [2026-07-10] Nettoyage du code mort de la gateway LLM

Suppression du client HTTP legacy et des brouillons de prompts qui ne servaient plus, désormais
que la chaîne de production passe entièrement par le SDK typé (`LLMGatewayClient` / `TaskResult`).

**Supprimé :** `client.py` (ancien `LLMClient` sync) et ses tests dédiés (`test_client_validate.py`,
`test_e2e.py`), l'orchestrateur manuel `test_main.py` qui les pilotait, et trois variantes de
template jamais chargées (`itinary_multi_agent{2,3,4}.md.j2` — le moteur ne résout que
`itinary_multi_agent`). Aucun impact sur la simulation : ces éléments n'étaient référencés que
par eux-mêmes.

**Conservé :** les shims de compatibilité `settings/models.py` et `tasks/llm_config.py`, toujours
utilisés par les notebooks d'analyse externes.

---

## [2026-07-10] Moins de fallbacks LLM : timeout élargi, bascule de modèle sur erreur, rafale de bootstrap lissée

Quatre changements pour récupérer les itinéraires qui retombaient inutilement sur le plan
par défaut (« itinéraire le plus rapide » non arbitré par le LLM) lors des pics de saturation.

**1. Timeout de tâche LLM porté de 30 s à 60 s.** La fenêtre d'attente du controller était
trop courte face au temps de récupération de la gateway : un provider en cooldown 60 s après
une 5xx « disparaissait » avant que le client puisse réessayer. Avec 60 s, le worker a le temps
d'absorber le cooldown + backoff ou de basculer sur un autre modèle avant l'abandon.

**2. Bascule automatique de modèle sur erreur non récupérable.** Sur une réponse illisible
(hors-schéma) ou un 4xx non lié au rate-limit, le batch n'échoue plus sèchement : le modèle
fautif est mis en cooldown court et la requête est rejouée sur un **autre** modèle via la
rotation. Un JSON invalide sur un provider peut ainsi réussir sur un autre.

**3. Rafale de bootstrap lissée.** Au démarrage, les ~centaines d'agents ne lancent plus leur
premier itinéraire tous en même temps : un plafond de concurrence (`bootstrap_concurrency`,
défaut 30) étale les calculs OTP+LLM en vagues, ce qui évite la cascade de 429/5xx qui générait
des centaines de fallbacks au pré-calcul.

**Avant :** un pic de 500 (ex. « 10 tâches échouées d'affilée, error 500 ») → ~460 agents en
fallback au pré-calcul.
**Après :** la rafale est lissée, les erreurs transitoires sont réessayées sur un autre modèle,
et le client attend assez longtemps pour bénéficier de ces reprises.

**4. Rappel : le plafond `max_tokens` (400) porte sur les tokens de sortie** (complétion), pas
sur le prompt — la limite est apprise puis le batch rejoué avec un budget réduit.

---

## [2026-07-10] Cockpit init : compteur d'activités ratées fiable, couverture cache tracée, avancement bootstrap détaillé

Trois améliorations du **Cockpit — Pilotage Simulation** autour de la phase d'initialisation.

**1. « Activités ratées faute de LLM » reste à 0 pendant l'init.** Le pré-calcul des
itinéraires (bootstrap) faisait déjà de vraies décisions LLM : quand la gateway saturait,
les fallbacks étaient comptés comme des activités ratées **avant même le démarrage**. Les
décisions sont désormais taguées `phase` (`bootstrap` / `live`) et le cockpit ne compte que
la phase `live`.

**Avant :** le compteur montait à plusieurs centaines pendant l'init (fallbacks du bootstrap).
**Après :** 0 avant le démarrage, il ne s'incrémente qu'une fois la simulation en marche.

**2. Pourquoi le cache LLM n'est pas à 100 % à l'init — tracé.** Ce n'est **pas** un problème
de taille (Qdrant n'a pas de plafond) mais de **couverture** : la moitié des agents n'avait
jamais eu sa 1ᵉʳ activité stockée, car le cache n'écrit que sur appel LLM réussi (déficit
auto-entretenu si la gateway sature au peuplement). Une ligne de couverture au démarrage
(`[cache] couverture LLM … N points, A agents couverts, S obsolètes`) + des gauges Prometheus
+ une classification des miss (*agent absent* vs *clé différente*) rendent la cause lisible.
Un `[ALARME]` signale les points hérités d'un schéma obsolète (`weekday=None`) qui gonflent
la base sans jamais servir.

**3. Avancement du bootstrap (phase 4) visible en direct.** Nouvelle rangée cockpit avec
progression, agents planifiés, taux de hit cache du bootstrap, vague d'anticipation courante
et trajets futurs pré-cachés.

---

## [2026-06-10] Réparation JSON malformé (Mistral)

`adapters/base.py` utilise désormais `demjson3` comme fallback quand `json.loads` échoue sur la réponse d'un provider (virgule manquante, JSON tronqué, etc.). Si la réparation réussit, l'appel se termine normalement avec un log `WARNING`; sinon, la `ProviderParseError` est levée comme avant.

**Avant :** `JSONDecodeError: Expecting ',' delimiter` → tâche en échec définitif.  
**Après :** `demjson3` répare le JSON malformé et le traitement continue.

---

## [2026-06-05] Réflexions agents opérationnelles (STM/LTM)

Les agents peuvent maintenant générer et stocker des réflexions à partir de leur mémoire
courte et longue durée. Les réflexions passent par la gateway LLM (cache sémantique,
load balancing, circuit breaker) et sont prioritaires sur les départs futurs.

**Avant :** `self.llm` toujours None → toutes les réflexions silencieusement ignorées.  
**Après :** les réflexions STM et LTM sont exécutées, retournées et persistées correctement.

---

## [2026-06-05] Cache OTP activé partout par défaut

Le cache persistant OTP est désormais actif dans tous les modes sans configuration
explicite. Les itinéraires O/D/heure sont réutilisés entre les runs, ce qui accélère
significativement le warm-up.

**Avant :** certaines configs d'expérience forçaient `otp_cache_enabled: false`,
désactivant silencieusement le cache.  
**Après :** la valeur par défaut (`True`) fait foi ; les 36 configs d'expérience ne
peuvent plus le désactiver par inadvertance.

---

## [2026-06-05] Observabilité unifiée des trois caches (OTP / OSMnx / LLM)

Une seule ligne de log `[cache] OTP X% · OSMnx Y% · LLM Z%` est émise en fin de
warm-up et à chaque sync, avec le détail des miss LLM par raison (`no_candidates`,
`code_not_in_options`, …). Permet de diagnostiquer rapidement un cache inefficace.

---

## [2026-06-04] Routage population simplifié — SQLite comme unique source de vérité

Le fichier de population ne stocke plus les routes calculées. Toutes les routes passent
par le cache SQLite OSMnx, ce qui évite les désynchronisations entre le fichier et le
cache et simplifie la génération de population (`generate_population.ipynb`).

---

## [2026-06-04] Mémoire long terme agents activée

Les réflexions quotidiennes (STM→LTM) et la self-reflection multi-jours sont
fonctionnelles. La mémoire est activée par défaut ; les événements sont écrits en
double (JSONL + CSV) pour faciliter l'analyse.

---

## [2026-06-03] Météo injectée dans chaque observation agent

Les agents reçoivent les conditions météo courantes dans chaque observation.
Le flag `timed_out` est ajouté dans `GamaArrivalsLogger` pour distinguer les
agents bloqués en attente TC (> 30 min) des arrivées normales.

---

## [2026-06-03] Données versionnées avec DVC

Population (`po_toulouse.small`, `population_samples`) et sorties eqasim sont
maintenant versionnées via DVC. Les données météo historiques Toulouse 2025-01
à 2026-04 sont incluses.

---

## [2026-06-03] Throttling scheduler corrigé + robustesse initialisation

La formule de throttling (`min(cap,(n/scale)^k)`) est plus stable sous forte charge.
Les endpoints `/reflect` et `/sync` répondent `not_ready` (au lieu d'une erreur 500)
si le scénario n'est pas encore initialisé.

---

## [2026-06-15] Prompts système en source unique (prompts.yaml)

Le texte des prompts système est désormais centralisé dans
`llm_module/prompts/prompts.yaml` (fusion avec l'historique de calibration),
au lieu d'être codé en dur dans les templates Jinja. Une carte `active:` désigne
la variante en production par catégorie ; promouvoir un prompt calibré ne demande
plus de modifier le code. Le template `itinary_multi_agent` ne porte plus que la
structure (boucle agents + `{{ schema }}`). Variante active initiale : `expert`.

---

## [2026-06-15] Cache LLM invalidé au changement de prompt système

Le cache sémantique LLM est désormais partitionné par empreinte du prompt système actif :
`data/cache/llm/<checksum>/<population>/`. Le checksum
(`PromptManager.active_prompt_checksum()`) change dès qu'une nouvelle variante de prompt est
promue, évitant de réutiliser des décisions obsolètes. Les anciens caches sont conservés.

## [2026-06-17] Aucun déplacement ne démarre le week-end

Un départ planifié tombant un samedi ou un dimanche est automatiquement reporté
au lundi suivant à la même heure (samedi -> +2j, dimanche -> +1j). Le décalage
est appliqué sur le `departure_time` dans `_compute_move_for_activity`, donc
l'itinéraire OTP, `expected_arrive_at` et le `schedule_at` côté GAMA en
découlent. Comportement activable via `agent.no_weekend_departures` (défaut: vrai).

---

## [2026-06-17] Repères temporels unifiés dans les logs (`[SIM_TIMING]`)

Trois lignes de log partagent désormais le tag commun `[SIM_TIMING]` avec un champ
`event=...` pour faciliter la recherche (`grep '\[SIM_TIMING\]'` ou `grep event=SIM_DAY`),
chacune horodatée par l'heure réelle (`real_time`) :
- `event=SIM_START` : réception de `/init` (lancement de la simu) ;
- `event=INIT_DONE` : fin de la phase d'init (bootstrap terminé) ;
- `event=SIM_DAY` : à chaque tranche de 24h de temps simulé écoulé depuis le départ,
  avec `sim_day`, `sim_time` et `real_elapsed` (temps réel cumulé) pour mesurer le débit
  de la simulation.

Implémenté via `helper.format_sim_timing(...)`, appelé depuis `handle/application.py`
(`/init`) et `simulation_controller.sync()` (borne 24h).

---

## [2026-06-24] Consommation de tokens traçable par jour simulé et économie du cache

Deux ajouts pour mesurer empiriquement la consommation de tokens et l'effet du cache :

- `llm_exchanges.jsonl` porte désormais `sim_ts` / `sim_day` (timestamp simulé repris de
  `AgentSpec.departure_timestamp`), permettant de ventiler les tokens par **jour de
  simulation** au lieu de l'horloge murale.
- Chaque hit du cache sémantique LLM est tracé dans `workdir/llm_cache_hits.jsonl`
  (`log_llm_cache_hit()`). Comme un hit ne génère aucun appel — donc aucune ligne dans
  `llm_exchanges.jsonl` —, ce fichier permet de compter les appels économisés et d'estimer
  les tokens épargnés.

Le notebook `scripts/analysis/llm_traffic_analyse.ipynb` ajoute un graphe
« tokens par jour vs limite journalière » (plafond 338 540 000 tokens en pointillé),
empilé par catégorie, avec l'économie de cache estimée si `llm_cache_hits.jsonl` est présent.

---

## [2026-06-24] Réalignement des agent_id mal formés par le LLM

Le modèle renvoyait parfois un `agent_id` mal formé dans les réponses `itinary_multi_agent`
(ex. `PERSONA 446264`, ou le nom du persona à la place du numéro). Comme le démultiplexage
des résultats matche par `agent_id` exact, ces agents étaient **silencieusement écartés** :
aucune recommandation de trajet ne leur était renvoyée, et les métriques de distance/mode
les ignoraient.

- **Worker** (`worker/task_worker.py`) : après validation de la sortie LLM, chaque `agent_id`
  inattendu est réaligné sur l'identifiant réel via sa partie numérique. Un réalignement est
  loggé en `warning`, un id non résolu (sans chiffre, ex. un nom) en `error`.
- **Prompt** (`prompts/templates/itinary_multi_agent.md.j2`) : l'en-tête persona passe de
  `--- PERSONA {id} ---` à `--- agent_id={id} ---` (le mot « PERSONA » incitait le modèle à le
  recopier), et une consigne explicite demande de recopier l'`agent_id` numérique à l'identique.
- **Schéma** (`prompts/schemas.json`) : `agent_id` documenté (« recopier l'id fourni, numérique
  uniquement, sans préfixe ni nom »).

---

## [2026-06-26] Calibration de prompt : Gemini de bout en bout & tableau de bord de présentation

Le notebook `scripts/models_influence/prompt_calibration_V4.ipynb` et son module
`prompt_calibration_lib.py` évoluent pour produire un support de présentation lisible.

- **Modèle unifié** : évaluation **et** génération de mutations passent sur
  `gemini-3.1-flash-lite-preview` (plus aucune dépendance Mistral). `generate_mutation`
  appelle désormais l'API generativelanguage. Le log affiche explicitement le modèle
  réellement utilisé (résolu depuis `default_model` du provider).
- **Tableau de bord** (`present_calibration_state`) affiché au run initial puis à **chaque**
  mutation (acceptée ou rejetée) : carte d'ablation colorée (vert=utile/rouge=nuisible),
  méta « pires écarts strate × mode » vs EMC², score global, scores L1 par dimension,
  barres distribution actuelle vs EMC² (hachuré), et évolution du score (points verts
  conservés / rouges rejetés).

---

## [2026-06-26] Cooldown 429 : respect du délai Gemini (corps JSON)

Sur un rate limit 429, le délai de retry était lu uniquement dans les headers
(`x-ratelimit-reset-requests`). Google Gemini ne renvoie pas ce header — il place le
délai dans le corps JSON — donc le cooldown retombait systématiquement sur le défaut de
60s, en ignorant un « retry in 6.6s » bien plus court.

`adapters/base.py` extrait désormais ce délai du corps (`extract_retry_delay_from_body`) :
champ structuré `error.details[].retryDelay`, puis repli sur le texte `"Please retry in Xs"`.
Le header reste prioritaire quand il est présent. Bénéficie à la fois au worker (durée de
cooldown du provider) et au notebook de calibration (qui lisaient tous deux le même attribut
`ratelimit_reset`).

---

## [2026-07-07] llm_module : 4 correctifs de fiabilité (batching, timing, circuit breaker)

Relecture complète du module → correction de quatre bugs :

- **Déclenchement des batchs (race condition)** : l'armement du compte à rebours reposait
  sur `queue_size == 1` ; deux requêtes simultanées sur une file vide pouvaient chacune
  observer une taille de 2 et aucune n'armait le dispatch (tâches bloquées jusqu'au timeout
  client). Un flag SETNX `batch_sched:{batch_key}` garantit désormais exactement un dispatch
  différé par cycle de batch ; le worker le libère au moment du pop (TTL en filet de sécurité).
- **`min_tpm_required` perdu** : le re-dispatch d'une file non vide après un batch réussi
  omettait la contrainte TPM — les tâches suivantes pouvaient partir vers un provider
  sous-dimensionné. L'argument est maintenant propagé.
- **Métrique `P4_4_ms` toujours à 0** : l'attente micro-batch était calculée en mélangeant
  `time.monotonic()` (uptime) et un timestamp epoch — résultat négatif clampé à 0. Calcul
  corrigé avec `time.time()`, et migration de `datetime.utcnow()` (naïf, déprécié) vers
  `datetime.now(timezone.utc)` dans les modèles et le worker.
- **Circuit breaker Google inopérant sur timeout** : l'adapter Google levait ses erreurs
  (timeout, réponse vide/bloquée) avec le nom de classe `"google"` au lieu du nom d'instance
  (`google_gemma42`, …) — le cooldown était posé sur une clé que personne ne consultait et
  l'instance fautive restait sélectionnée. Les exceptions portent désormais `_instance_name`.

## [2026-07-07] llm_module : restructuration en package (ports & adapters)

Mise en œuvre du CR [llm-module-package-refactor.md](arch/llm-module-package-refactor.md)
(phases 0 à 5). Le contrat HTTP consommé par GAMA est inchangé.

- **Packaging** : `pyproject.toml` (installable `pip install .`), 12 dépendances runtime au
  lieu de ~45 — image Docker du gateway fortement allégée. Extras `[test]` et `[monitoring]`.
- **Plus d'effets de bord à l'import** : Settings construits explicitement (`get_settings()`),
  fabriques `create_app()` / `create_celery_app()`, reset des fenêtres RPM déplacé dans le
  lifespan de l'API (un redémarrage de worker ne remet plus les quotas à zéro), suppression
  du couplage caché `from settings import settings` dans la télémétrie.
- **Découpage du broker** : `redis_broker.py` (~30 fonctions libres) remplacé par 4 classes
  (`RedisTaskStore`, `RedisRateLimiter`, `RedisBatchQueue`, `RedisMetricsSink`) derrière des
  interfaces Protocol (`ports/`), avec équivalents `InMemory*` pour tester sans Redis.
- **Perf** : compteurs worker migrés vers un hash Redis (`wmetrics`) — 1 `HGETALL` par scrape
  Prometheus ; adapters mis en cache avec client httpx partagé (keep-alive entre appels LLM) ;
  clé API Google en header `x-goog-api-key` (plus de clé dans les URLs de logs).
- **SDK typé** : `LLMGatewayClient.execute()` → `TaskResult` pydantic (fini les dicts bruts,
  `"EXPECTED_ERROR"` et clés `_post_ms` injectées) ; `llm_agent.py` migré. L'ancien `LLMClient`
  reste pour les tests E2E.
- **Frontières vérifiées** : `core/` pur (batching, SWRR) + contrats import-linter en CI
  possibles (`lint-imports --config llm_module/pyproject.toml`).
- Tests : 197 unitaires verts (52 ajoutés). À rejouer avant merge : `docker compose build`
  + `test_e2e.py --burst 20`.

## [2026-07-07] llm-agents : correctifs de fiabilité (revue de code)

Quatre corrections issues de la relecture complète du module `llm-agents` :

- **Boucle d'envoi WebSocket robuste** : le handler d'exception de `publish_loop`
  référençait un attribut inexistant (`self.reconnect_interval`) — toute exception
  générique tuait définitivement la boucle d'envoi des actions bootstrap vers GAMA.
- **Worker de fallback annulé sur ré-init** : `set_scenario` annulait le wrapper
  `start_worker` (déjà terminé) au lieu de la vraie boucle de scan ; sur des `/init`
  successifs, l'ancienne boucle continuait de scanner l'ancienne population. Nouveau
  `stop_worker()` sur le scénario, appelé avant remplacement.
- **Persistance de la mémoire long-terme réparée** : les `MemoryEntry` étaient
  sérialisées en chaînes (`json.dumps(default=str)`) — irrécupérables au redémarrage,
  la mémoire épisodique repartait de zéro à chaque restart. Sérialisation explicite
  `to_dict()`/`from_dict()` (round-trip testé), fichiers de l'ancien format tolérés,
  et correction du cleanup >10 000 entrées et de `get_user_stats` qui traitaient les
  entrées comme des dicts (TypeError).
- **Clé du cache OTP persistant complétée avec `include_bike`** : un itinéraire calculé
  pour un agent sans vélo pouvait être resservi à un agent avec vélo (option vélo
  silencieusement absente des choix du LLM). Effet de bord : les entrées existantes du
  cache OTP deviennent froides (nouveau format de clé) — le cache se repeuple au premier run.

Tests : round-trip `MemoryEntry`, save/load métadonnées LTM, annulation worker,
différenciation des clés de cache, + 16 tests unitaires existants verts.

## [2026-07-08] Fiabilité pipeline LLM : corruption cache, délais 429, alarmes

Diagnostic d'une simulation où 80 % des agents restaient inactifs (backlog de
planification à 886/901 après 1h30) : providers LLM en rate-limit, cache sémantique
à 0 % de hit, backpressure inopérant. Trois correctifs :

- **Cache sémantique LLM — accès Qdrant sérialisé** : le client Qdrant embarqué n'est
  pas thread-safe ; les lookups/stores concurrents (via `asyncio.to_thread`)
  corrompaient l'index ("operands could not be broadcast", erreurs SQLite) et le cache
  ne servait plus aucune décision. Verrou `_db_lock` autour de `query_points`/`upsert`,
  plus alarme après 5 erreurs Qdrant consécutives.
- **Délai 429 réellement pris en compte** : le gateway ignorait le header standard
  `retry-after` et `x-ratelimit-reset-tokens` (les 429 Groq portent sur les tokens),
  et le fallback corps ne matchait pas les messages Groq ("try again in 16m7.68s") ni
  les formats `h`/`ms` (quotas journaliers TPD). Le cooldown provider est désormais
  calé sur le délai annoncé (clampé à [10s, 1h]) avant re-routage vers un autre modèle.
- **Alarmes de saturation** (`[ALARME]`, niveau ERROR, visibles via `make error`) :
  backlog > 50 % de la population dans `/sync` (avec min_interval et coefficients,
  poussée aussi vers la console GAMA), tous providers saturés côté worker gateway,
  et 10 échecs de tâches consécutifs côté SDK client.

Tests : 208 tests `llm_module` verts, dont nouveaux cas de parsing (`retry-after`
brut, `reset-tokens` prioritaire, durées `2h37m12.5s`, `140ms`, `16m7.68s`).

## [2026-07-08] Backpressure /sync : seuil relatif à la population

La formule de throttling introduite le 11 juin (`min(cap, (n / (120×pop/100))^3.7)`)
rendait le frein inatteignable : le backlog ne dépassant jamais la population, le
seuil absolu (1200 pour 1000 habitants) n'était jamais franchi — 0.33s de pause avec
886/901 agents en attente. Nouvelle formule `cap × min(1, backlog/population)^k`
extraite dans `backpressure.py` (fonction pure) : ~2.3s à 50% de backlog, ~19s à 89%,
cap (30s) à pile pleine, identique quelle que soit la taille de population. Le
coefficient `min_internal_coeff_scale`, devenu sans objet, est supprimé des settings.

Tests : `tests/test_backpressure.py` (10 cas) vérifie l'invariance du délai à ratio
de remplissage égal, l'atteignabilité du cap à pile pleine, la croissance monotone
avec le backlog et le cas réel du run 2026-07-07 (886/1000 → ~19.2s).

## [2026-07-08] llm-agents : correctifs secondaires et optimisations (revue de code, suite)

Implémentation des points #5–#8 et #11–#14 de la [revue de code](revue-llm-agents-reste-a-faire.md) :

- **Fallback LTM sans ChromaDB réparé** : `_init_shared_index` référençait une variable
  jamais définie dans la branche "simple storage" (NameError au premier démarrage sans index).
- **Mode SOLARI + récursion réparé** : `do_get_iteraries_v1` n'acceptait pas `include_bike`
  (TypeError systématique quand `recursion_search_depth > 0`).
- **Plus de trajet perdu sur échec WebSocket** : le rollback de `_push_planned_move` restaure
  le move calculé (LLM + OTP), et le scan de fallback détecte l'état Idle+plan pour retenter
  l'envoi au lieu de tout recalculer.
- **Cache sémantique LLM aligné sur l'intention** : suppression du rejet par seuil de
  similarité (`below_threshold`) — le filtre déterministe (agent + activité + tranche 10 min
  + hash options/météo) identifie déjà le contexte ; la similarité ne sert plus qu'à classer
  les candidats multiples. La LTM peut évoluer entre les runs sans invalider les décisions.
- **Persistance LTM allégée** : écriture des métadonnées par rafale (debounce 30 s + flush à
  l'éviction LRU) au lieu d'une réécriture complète du fichier à chaque entrée ; sérialisation
  unique ; écritures déportées hors de l'event loop ; `print()` remplacés par loguru.
- **Requêtes LTM filtrées côté vector store** : le retriever passe un filtre `person_id`
  (clause `where` Chroma) avec `top_k×5` candidats au lieu de rapatrier jusqu'à 500 nœuds
  globaux puis filtrer en Python — le recall par agent ne dépend plus du peuplement global.
- **I/O fichier hors event loop** : les écritures CSV/JSONL par événement (moves, arrivées
  GAMA, hits du cache LLM, états d'agents) passent par `asyncio.to_thread` — plus de blocage
  des coroutines aux heures de pointe.
- **Session HTTP OSMnx réutilisée** : une `aiohttp.ClientSession` partagée (keep-alive)
  remplace la création d'une session par requête vers les réplicas osmnx.
- **Tâches de fond protégées du GC** : nouveau helper `create_background_task` (référence
  forte jusqu'à complétion) appliqué à tous les `asyncio.create_task` fire-and-forget
  (planification, push, stores de cache, reconnexion WebSocket, boucle d'envoi).

Tests : rollback push, debounce LTM, référence des tâches de fond, signatures — verts ;
16 tests unitaires existants verts.

## [2026-07-08] llm-agents : métrique minuit et hygiène des logs (#9, #10)

- **Métrique `agent_scheduling_lag_seconds` corrigée au passage de minuit** : le delta
  envoi−cible (deux horaires mod 86 400) est normalisé dans [−43 200, +43 200] — un envoi
  à 00:05 pour une cible 23:55 compte désormais +600 s au lieu de −85 800 s.
- **Logs réparés et nettoyés** : deux `logger.warning("... %s", …)` (format printf ignoré
  par loguru → message affiché littéralement) convertis en f-strings dans la préparation
  de population ; suppression des logs de diagnostic `[trace]` marqués « à retirer »
  (factory, wrapper de cache OTP, init du cache par population).

## [2026-07-08] Anti-saturation gateway : quotas journaliers, timeout 30 s, backpressure SDK

Diagnostic du run où plus aucune décision LLM ne revenait après quelques jours simulés :
les prompts grossissent avec la mémoire (≈675 → 2000 tokens), les quotas free-tier
s'épuisent et le pipeline dégénérait en timeouts/plans par défaut (jusqu'à 99 % d'échecs
LLM le dernier jour). Trois correctifs :

- **Quotas journaliers RPD/TPD appliqués** (jusque-là purement informatifs) : dès qu'un
  provider atteint son `rpd_limit`/`tpd_limit`, il est écarté de la rotation jusqu'à minuit
  UTC au lieu d'être re-sollicité toutes les `disable_timeout` secondes. Compteurs journaliers
  UTC dans Redis (requêtes à la réservation, tokens réels après l'appel) ; `/health` expose
  `daily_requests`/`daily_tokens`/`quota_exhausted`.
- **Timeout tâche LLM 90 s → 30 s** : fallback plan par défaut plus rapide, la simulation ne
  bloque plus 90 s par calcul quand la gateway est muette. Budget de saturation-retry du
  worker recalé sous 30 s.
- **Backpressure SDK sur alarme** : quand l'alarme « 10 échecs consécutifs » se déclenche,
  le client suspend les nouvelles soumissions jusqu'au drainage de la pile in-flight sous
  20 % de `worker_concurrency`, laissant la gateway respirer avant de re-charger.

Tests : quotas RPD/TPD (in-memory + Redis) et drainage backpressure verts ; suite
`llm_module` (208 tests) verte.

---

## [2026-07-08] Cache OSMnx réutilisable au rejeu

Un rejeu de simulation recalculait tous les trajets (Pass 2, ~0,4 s/route) au lieu de
frapper le cache. Deux causes corrigées :

- **Clé voiture sans date absolue** : `OsmnxPersistentCache.make_key` n'inclut plus la date
  (`YYYY-MM-DD`), seulement le **jour de la semaine + tranche horaire** — la granularité réelle
  du facteur de congestion. Deux runs à des dates calendaires différentes mais même weekday
  réutilisent les mêmes trajets. Marche/vélo restent indépendants du temps (coords + mode).
- **Échantillonnage d'agents déterministe** : la sélection aléatoire des agents depuis la
  sortie eqasim utilise désormais une seed fixe (`data.population_sample_seed`, défaut 42) via
  un RNG local. Un rejeu retire exactement le même sous-ensemble d'agents → mêmes coordonnées
  → le cache SQLite fait hit au lieu de recalculer.

Note : les entrées voiture antérieures (clé incluant la date) ne sont plus adressées et se
repeuplent au premier run.

---

## [2026-07-08] Mode drainage /sync : GAMA retenu jusqu'à vidage de la pile à 80 %

Le frein progressif du `/sync` ne retenait GAMA que ~2.3 s par step à 50 % de backlog :
le temps simulé filait devant le pipeline LLM et les agents restaient inactifs faute de
plan. Ajout d'un **mode drainage à hystérésis** (`update_drain_mode`, `backpressure.py`) :

- Enclenché quand la pile atteint `drain_trigger_ratio` (50 %), il retient chaque réponse
  `/sync` jusqu'au cap (30 s, limite du read timeout HTTP de GAMA) en ré-échantillonnant
  la pile chaque seconde.
- Relâché seulement quand la pile repasse sous `drain_release_ratio` (20 %, pile vidée à
  80 %) — entre les deux seuils GAMA reste bridé à ~1 step par cap.
- Traces `[drain]` (WARNING enclenchement/cap atteint, INFO relâchement) ; réglages dans
  `WorldConfig` (`drain_trigger_ratio: 0` pour désactiver).

Doc : `docs/arch/llm-inference.md` § « Mode drainage /sync ». Tests :
`tests/test_backpressure.py` (15 verts).

---

## [2026-07-08] Fix troncature des réponses LLM à max_tokens sur les batches

Les batches `stm_reflection` de 10 agents (~500-1800 tokens de sortie par agent)
saturaient le `max_tokens` fixe de 4096 : réponse JSON coupée en plein milieu →
`JSONDecodeError` à offset constant (char 13158/14704 ≈ 4096 tokens), et batch entier
perdu. Deux corrections dans le gateway :

- **Budget de sortie proportionnel au batch** (`task_worker._execute_batch`) : le
  `max_tokens` client est désormais un budget par tâche, multiplié par le nombre
  d'agents fusionnés, borné par le nouveau réglage `max_output_tokens` (16 384) puis
  par la capacité du provider.
- **Détection de troncature typée** (`BaseAdapter._check_openai_finish_reason`) : les
  adapters mistral/groq/cerebras/openai vérifient `finish_reason == "length"` et lèvent
  `max_tokens_truncation` (503, retryable) au lieu d'un parse error trompeur — couvre
  aussi le `content` vide des modèles thinking (GLM-4.7) dont le budget part en
  raisonnement.

Doc : `docs/arch/llm-inference.md` § « Budget de sortie proportionnel au batch ».
Tests : `tests/test_adapter_base.py` (42 verts).

Complément : la jauge `activities_to_compute_count` compte désormais les agents Idle
sans plan **en direct** (plus de snapshot figé au dernier sync) — indispensable pour que
le mode drainage voie la pile baisser pendant qu'il retient la réponse `/sync` et rende
la main dès le seuil de relâchement. Clarification doc : avec l'horizon glissant 24h,
un agent qui termine son trajet reçoit immédiatement son move suivant et passe `ready` ;
un taux d'`inactive` durable est bien le symptôme d'un précalcul en retard (et non un
état légitime), à l'exception des activités consécutives au même endroit (`legs=[]`).

Réglage de la courbe de frein (demande du 2026-07-08) : exposant `k` passé de 3.7 à
**1.5** pour un freinage précoce et progressif (~1 s à 10 % de pile, ~2.7 s à 20 %,
~5 s à 30 %, ~7.6 s à 40 %, ~10.6 s à 50 %, ~21.5 s à 80 %). Le mode drainage et
l'alarme backlog se déclenchent désormais ensemble à **80 %** (`drain_trigger_ratio`)
et se relâchent au retour sous **20 %** (`drain_release_ratio`), l'alarme n'ayant plus
de seuils codés en dur.

## [2026-07-08] Fix : cache OSMnx inactif pendant le Pass 2 de génération de population

Le cache persistant OSMnx n'était initialisé qu'**après** l'écriture du fichier
population : lors d'une régénération, le Pass 2 (calcul des temps de trajet pour
l'ajustement des plannings) recalculait toutes les routes via OSMnx sans lire ni
alimenter le cache. L'initialisation (`_init_osmnx_cache`) est déplacée en tête de
`_prepare_population`, avant tout routage : le Pass 2 lit et remplit désormais le
cache, et une régénération ultérieure réutilise les routes déjà calculées.

Doc : `docs/arch/cache-memory.md` § « cache persistant OSMnx ».

## [2026-07-08] Plafond de complétion par provider (max_output_tokens) auto-appris

Les batchs `stm_reflection` échouaient en HTTP 400 sur `groq_llama4`
(`max_tokens` calculé = 16 384 > limite de 8 192 de `llama-4-scout`). Chaque provider
porte désormais un champ optionnel `max_output_tokens` dans `providers.yaml` (plafond
de complétion du modèle) : le worker borne le `max_tokens` envoyé à cette valeur, et
le load balancer écarte les providers incapables de servir le budget de sortie d'une
tâche (filtre `min_output`, même mécanique que `min_tpm`). Si un provider répond
malgré tout 400 « max_tokens must be ≤ N », la limite N est **apprise
automatiquement** : config ajustée en mémoire, ligne écrite dans `providers.yaml`
(commentaires préservés, écriture atomique, persistée sur l'hôte via le bind mount)
et batch rejoué au lieu d'échouer définitivement.

Doc : `docs/arch/llm-inference.md` § « Plafond de complétion par provider ».

## [2026-07-08] Cockpit de pilotage Grafana

Nouveau dashboard `cockpit.json` regroupant en une page l'état de la simulation :
avancement de l'init (5 étapes), remplissage de la pile et frein backpressure,
délai réel par step, **agents bloqués** (aucune planification réussie depuis
> `world.stuck_agent_threshold_hours` h simulées, défaut 20 h), état et **quotas
jour** des providers (ratio d'usage RPD), taux de hit des caches (LLM / OTP /
OSMnx) et **dernières erreurs LLM**.

Nouvelles métriques exposées côté gateway (`llm_provider_rpm/rpd/tpd_limit`,
`requests_today`, `tokens_today`, `daily_usage_ratio`, `quota_exhausted`) et côté
contrôleur (`controller_init_stage/progress_ratio`, `backpressure_interval_seconds`,
`backlog_fill_ratio`, `drain_mode_active`, `agents_stuck`). Les messages d'erreur
bruts, non stockables dans Prometheus, transitent par un ring buffer Redis
(`llm:recent_errors`) exposé via `GET /errors/recent` et affiché grâce au plugin
Grafana *Infinity*.

Doc : `docs/arch/monitoring.md`.

---

## [2026-07-08] Fiabilité du push GAMA : rollback sur envoi non délivré + watchdog d'arrivée

L'analyse du run 15:41 a montré ~250 agents « zombies » : `send_message` avale les
exceptions WebSocket et retourne `False`, que `_push_planned_move` ignorait — le push
était annoncé réussi ([push] dans les logs) alors que GAMA n'avait jamais reçu le trajet
(3 coupures WS 1006 pendant le run). L'agent restait « en déplacement » côté Python,
inactif côté GAMA, invisible de la pile de backpressure, du drainage et du scan.

- **Rollback sur `False`** : `_direct_push` propage le booléen de `send_json` et
  `_push_planned_move` traite un retour `False` comme une exception → rollback complet,
  le scan de fallback retente le push après reconnexion (le trajet calculé n'est pas perdu).
- **Watchdog d'arrivée** : chaque push arme `heading_expected_arrive_at` ; si le temps
  simulé dépasse l'échéance de plus de `world.arrival_watchdog_hours` (défaut 1 h sim),
  le scan lève `[ALARME] Arrivée perdue`, force la fin d'activité et remet l'agent dans
  le circuit. Couvre aussi les pertes silencieuses (socket moribonde avant détection
  keepalive, message perdu côté GAMA). Métrique `controller_lost_arrivals_recovered_total`.

Doc : `docs/arch/agents-lifecycle.md` § « Fiabilité du push ».

Analyse du run 18:29 (correctifs actifs) : le rollback (67 reprises) et le watchdog
(339 agents récupérés) fonctionnent, mais les coupures WebSocket persistaient — cause
racine identifiée : **blocages de l'event loop asyncio de 7-20 s** qui faisaient expirer
le keepalive (`ping_timeout=10s`). Deux compléments :

- **`ping_timeout` porté à 60 s** (`handle/websocket.py`) : un stall ponctuel ne ferme
  plus la socket ; une vraie coupure reste détectée en ~1 min et couverte par le watchdog.
- **Moniteur d'event loop** (`controller_event_loop_lag_seconds`) : mesure en continu la
  dérive de la boucle asyncio, `[ALARME]` en ERROR au-delà de 5 s de blocage pour
  identifier l'opération synchrone fautive.

## [2026-07-09] Reset propre au remplacement de scénario (stop GAMA → nouveau /init)

Un stop de simulation GAMA ne stoppe pas le process Python (pas d'endpoint `/stop`) :
le `/init` suivant remplace le scénario. Deux résidus de l'ancien run pouvaient
contaminer le nouveau, les `person_id` étant identiques d'un run à l'autre (même
population, même seed) :

- **Tâches en vol de l'ancien scénario** : `stop_worker()` n'annulait que la boucle de
  scan — les planifications LLM/OTP déjà lancées allaient au bout et poussaient leurs
  trajets périmés à la nouvelle simulation. Toutes les tâches fire-and-forget du
  contrôleur (planification, refill, push, réflexions, checkpoints) sont désormais
  suivies dans `_inflight_tasks` et annulées en bloc au remplacement.
- **Buffer de retry du `publish_loop`** : les actions non délivrées (socket morte au
  stop) restaient en attente et étaient rejouées vers le nouveau run à la reconnexion.
  Le buffer (`LoopContainer._pending`) est purgé par `set_scenario()` avec un WARNING
  donnant le nombre d'actions écartées.

Doc : `docs/arch/agents-lifecycle.md` § « Arrêt de simulation et remplacement de scénario ».

## [2026-07-09] Ordonnancement EDF et contre-pression prédictive pilotée par les échéances

Deux causes d'effondrement des runs longs corrigées : le service FIFO du contrôleur
(un refill lointain pouvait bloquer une replanification urgente derrière un jeton de
concurrence) et un frein `/sync` aveugle aux échéances (freinait trop tard sur
épuisement de quota, et pour rien quand le backlog n'était que des refills non urgents).

- **Dispatcher EDF** (`simulation_controller.py`) : les tâches de planification sont
  servies par échéance croissante (heure de départ simulée) via une file de priorité
  (`_edf_heap`) consommée par `world.worker_concurrency` tâches, au lieu du sémaphore
  FIFO. Une replanification urgente passe devant un refill d'horizon lointain ; un push
  déjà calculé (deadline 0) passe devant tout. Flag `world.edf_enabled` (défaut `true`,
  `false` = spawn direct historique). File vidée et consommateurs annulés au
  remplacement de scénario. Le sémaphore reste utilisé par le bootstrap.
- **Contre-pression prédictive** (`backpressure.py`, `application.py`) : le `/sync`
  n'est retenu que si le test de faisabilité EDF (`edf_feasibility` : `T_k = k/D` vs
  `slack_k = (d_k − now_sim)/R`, marge `world.predictive_margin`) annonce une échéance
  menacée — vitesse maximale sinon (le frein `cap·ratio^k` est court-circuité). Le débit
  `D` est une EWMA des complétions (`ThroughputEwma`, `tau` = `world.throughput_ewma_tau_s`,
  plancher `world.throughput_floor_per_s`), le rythme `R` une EWMA du `sim_wall_clock_ratio`
  figée pendant la rétention. Le mode drainage à hystérésis reste le filet de sécurité ultime.
- **Notification GAMA** (topic `system/throttle`, hystérésis) : au-delà de
  `world.throttle_notify_threshold_s` de rétention cumulée, Python pousse le débit LLM
  réel et la vitesse de simulation, rafraîchi toutes les `world.throttle_notify_refresh_s`,
  levé au premier `/sync` sans rétention. Globales GAMA `THROTTLE_ACTIVE` /
  `LLM_RATE_PER_MIN` / `SIM_RATIO_PYTHON` (`Settings.gaml`, `LLMAgent.gaml`).
- **Observabilité** : 6 nouvelles jauges Prometheus (`controller_throughput_tasks_per_min`,
  `controller_edf_queue_depth`, `controller_t_estimate_seconds`,
  `controller_min_slack_sim_seconds`, `controller_predictive_hold_seconds`,
  `controller_deadline_misses_total`), renseignées même contrôle prédictif désactivé
  (phase d'observation pour calibrer `tau` et la marge).

Doc : `docs/arch/agents-lifecycle.md` (§ Dispatcher EDF, § Contre-pression prédictive),
`docs/arch/monitoring.md` (métriques + réglages). Tests : `tests/test_backpressure.py`
(EWMA + faisabilité EDF), `tests/test_edf_dispatcher.py` (ordre EDF).

## Outil de debug — Rapport de santé du dernier run

- **`scripts/debug/run_report.py`** : génère un rapport markdown « agent-ready » condensant
  les signaux essentiels au debug d'un run (`experiments/current` par défaut) — top erreurs/
  warnings normalisés d'`app.log`, matrice santé LLM (erreurs par provider × statut HTTP,
  taux de 429), latence pipeline (percentiles + détection de backlog), activité des agents
  (inactifs dans le temps), décisions modales & fallbacks, arrivées & timeouts. Une section
  `🚨 ALARMES` en tête synthétise les anomalies franchissant les seuils (ajustables en tête
  de script). Stdlib only, tolérant aux fichiers manquants.
- Exposé via `make report [RUN=… OUT=…]` et la skill Claude `/debug-run`.
- Limite connue : ne lit que les artefacts sur disque ; les logs des conteneurs Docker
  (api, worker, otp, osmnx) ne sont pas encore centralisés dans `app.log` (chantier suivant).

## Logging centralisé par service + analyse capacité LLM + digest live GAMA

- **Logs centralisés par conteneur** : `configure_logging()` (`llm_module/telemetry/logger.py`)
  ajoute un sink fichier `APP_WORKDIR/<SERVICE_NAME>.log` (même format qu'`app.log`) quand
  `SERVICE_NAME` est défini. `docker-compose.yml` renseigne `SERVICE_NAME`/`APP_WORKDIR` pour
  `api` (→ `api.log`) et `worker` (→ `worker.log`) ; le controller garde `app.log`. Tous
  atterrissent dans le dossier du run et sont agrégés (avec tag `[service]`) par
  `scripts/debug/run_report.py`. Sinks non-Python (`otp*`, `osmnx*`, `redis`) : via
  `docker compose logs`.
- **`scripts/debug/llm_capacity.py`** (`make capacity`, skill `/debug-run`) : analyse
  « débit vs capacité » LLM du run, 100 % à partir des logs existants — demande avant/après
  micro-batching (agents/min vs prompts/min via le champ `response` de `llm_exchanges`),
  contre-pression prédictive EDF parsée depuis `[predictive]` (débit D, pile, T d'écoulement,
  `slack_min` = temps simulé restant sur la tâche critique), épisodes `[BACKPRESSURE]` /
  `[ALARME] Gateway`, et saturation 429 par minute et par provider. Section `🚨 ALARMES`
  en tête (risque d'échéance, saturation soutenue).
- **Digest de capacité poussé à GAMA** (`handle/application.py`) : tous les 10 `/sync`, le
  controller envoie sur `system/log` une ligne synthétique `📊 [cycle N] cache LLM … · débit
  … req/min · backlog … · agents actifs/inactifs`. Signaux cheaply available en-process
  (débit `throughput_per_s`, cache `get_llm_cache_stats`, états agents) ; émission gardée
  (n'échoue jamais un `/sync`). Intervalle : constante `_DIGEST_EVERY_N_SYNC`.

## Outil de debug — Analyse de la phase d'initialisation

- **`scripts/debug/init_report.py`** (`make init`, skill `/debug-run`) : rapport markdown
  ciblé sur le **démarrage** de la simulation, complémentaire de `run_report` (santé globale)
  et `llm_capacity` (débit LLM). Dérivé 100 % d'`app.log`, stdlib only, tolérant aux fichiers
  manquants. Contenu :
  - **Timeline des 5 étapes d'INITIALISATION** (SIM_START → INIT_DONE) avec la durée et la
    part de chacune ; repère l'étape dominante (quasi toujours le bootstrap `4/5`).
  - **Câblage & réchauffage des 3 caches persistants** (OTP, OSMnx, LLM sémantique) :
    activés ? chemins ? taux de hit atteint en fin d'init via la ligne de résumé combiné
    `[cache] OTP … · OSMnx … · LLM …` ; coût du chargement du modèle d'embedding.
  - **Bootstrap** : nombre d'agents pré-calculés, vagues d'anticipation, futurs déplacements
    pré-cachés, montée du taux de hit cache (cold → warm) et coût par type d'activité.
  - **Bugs d'init** avec section `🚨 ALARMES INIT` en tête : stalls de l'event loop
    (I/O synchrone du bootstrap → coupures WebSocket 1006), thrashing du cache métadonnées
    LTM (évictions + `gc.collect()` en boucle, `llm/longterm.py`), OD injoignables.
  - Exposé via `make init [RUN=… OUT=…]` et intégré à la skill `/debug-run`. Seuils
    d'alarme ajustables en tête de script.

## Cache LLM hybride et optimisation de la phase d'initialisation

L'init d'une population de 901 agents prenait ~19 min alors que les caches (OTP, OSMnx, LLM)
affichaient un taux de hit de ~100 % et que seuls 75 appels LLM réels avaient lieu. Le temps
était intégralement consommé par la machinerie entourant le cache, entièrement sérialisée :
un embedding `all-MiniLM-L6-v2` (~318 ms, sérialisé par `_embed_lock`) et une requête
ChromaDB de mémoire long terme étaient payés sur *chaque* décision, y compris les cache hits.

- **Cache sémantique LLM hybride.** Le lookup applique d'abord un filtre déterministe sur les
  conditions factuelles (agent, activité, catégorie de jour, tranche de 10 min, hash des
  options et de la météo), puis :
  - *LTM vide* (tout le bootstrap) : correspondance exacte par `scroll` clé-valeur, **sans
    embedding** (~0,1 ms contre ~324 ms). Sans souvenir, deux décisions prises dans les mêmes
    conditions sont identiques.
  - *LTM remplie* : recherche par similarité cosinus entre la mémoire courante de l'agent et
    celle qui a produit la décision stockée, avec rejet sous `cache.semantic_threshold`.
    L'agent tient donc compte de son vécu au lieu de rejouer indéfiniment sa première
    décision — ce que faisait l'ancienne clé, aveugle à la mémoire.
  Les deux familles de points sont étanches (`memory_empty` fait partie du filtre).
- **Le payload LLM (et sa requête ChromaDB) n'est plus construit sur le chemin nominal**
  quand la mémoire est vide : uniquement en cas de miss.
- **Nouveau champ de filtre `weekday`** : semaine et week-end ne partagent plus leurs décisions.
- **Fin du thrashing du cache métadonnées LTM** : `long_term_max_loaded_metadata` passe de 200
  à 5000 (nouveau réglage `agent.long_term_max_loaded_metadata`, jusqu'ici non câblé). En
  dessous du nombre d'agents, chaque décision provoquait une éviction. Le `gc.collect()` par
  éviction (~110 ms, exécuté dans l'event loop, ~2600 fois par init) est supprimé : il causait
  les stalls de la boucle asyncio (jusqu'à 148 s) et les coupures WebSocket 1006.

⚠️ Le filtre du cache gagne les champs `weekday` et `memory_empty` : les caches antérieurs ne
les portent pas et ne seront jamais retrouvés. Supprimer `data/llm_cache/` avant un run.

## Garde-fou TPM & débit des providers Groq

- **Réservation TPM glissante (60 s)** ajoutée au rate-limiter, en plus du RPM. `tpm_limit`
  devient un plafond dur appliqué avant chaque appel (réservation atomique RPM+TPM en un seul
  script Lua, restituée sur échec), et non plus un simple filtre de routage. Chaque provider
  expose `tpm_estimate_per_request = batch_max_agents × (assumed_prompt_tokens +
  assumed_output_tokens)`. Élimine le flot de **429** des providers dont le `rpm_limit`
  dépassait la capacité tokens réelle. Providers sans `tpm_limit` non bridés.
- **`groq_qwen` / `groq_llama31`** (free tier, TPM 6 000 → ~2 req/min) : `rpm_limit` ramené de
  60/30 à **2** et `weight` de 1.0 à **0.5**, alignés sur leur vraie capacité — ils causaient
  ~78 % des 429 pour une contribution marginale.

## Indicateur d'activités ratées faute de réponse LLM

- Nouveau compteur `agent_activity_decisions_total{outcome}` (issue de chaque activité
  planifiée : `llm`, `llm_fallback`, `single`, `no_solution`, `no_move`) émis au point de
  décision du contrôleur. Le **cockpit ③** (« Agents bloqués ») gagne une rangée : part et
  nombre d'activités dégradées faute de LLM (`llm_fallback` → index par défaut) et le débit
  fallback/min.
- Le **move-log** (`moves.csv`) porte désormais `ID Personne` et `ID Activité`. Le rapport de
  run (`run_report.py`, skill `/debug-run`) ajoute une section **« Couverture des activités
  par jour »** : les activités étant récurrentes et non datées, on vérifie que chaque activité
  d'un agent s'exécute chaque jour de sa plage — décomptant les activités *dégradées* (sans
  LLM) et *manquées* (aucune exécution ce jour-là), avec alarmes dédiées.

SESSION ENDED
