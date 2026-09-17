# Ticket 070 — Des accidents tirés au sort sur les axes, et le retard qu'ils font subir

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-14, **en cours** depuis le même jour.
>
> **CE QUI EST LIVRÉ (2026-09-14, défaut basculé le 2026-09-15).** Un interrupteur
> « Accidents sur les axes » dans l'IHM GAMA, **VRAI par défaut** depuis le 2026-09-15,
> persisté et consigné dans le `scenario_params.yaml` de chaque run. Les sept tickets ouverts
> qui lancent un run GAMA portent désormais un avertissement sur ce paramètre (018, 032, 033,
> 048, 071, 075, 079).
> Les accidents **existent** : tirés selon une loi estimée sur BAAC 2019-2024 (heure, jour de
> semaine, classe de vitesse), posés sur une arête du graphe, journalisés avec leurs compteurs
> y compris à zéro. Spec `specs/accidents-interrupteur-gama.md`, 25 tests, doc
> `docs/arch/accidents-sur-les-axes.md`.
>
> **LIVRÉ LE 2026-09-15 — LE RETARD ET LA POSE.** Un accident allonge désormais les
> itinéraires qui le traversent (travail C), avec ses **deux gardes de cache** livrées dans le
> même geste (D et E) : sans elles, une durée perturbée serait resservie à des runs qui n'ont
> rien demandé, et un agent retardé rejouerait sa décision d'avant. L'expérimentateur peut
> **poser** un accident choisi depuis l'IHM ou par `POST /accidents` (travail F).
>
> **CE QUI RESTE.** Le **souvenir** du retard (travail G) — il faudrait que l'information
> remonte du routage jusqu'à l'agent, et la chaîne mémoire est en refonte (tickets 071, 075).
> Le **contournement**. Le **facteur météo** (calculé, **rejeté**, neutre) et la vérification
> de **linéarité** en taille de cohorte.
>
> ⚠ **Les runs d'avant et d'après le 2026-09-15 ne sont pas comparables** : le régime est actif
> par défaut et les accidents ralentissent.
>
> **L'article promet déjà ce mécanisme.** Le chapitre 3 range « un bouchon né d'un incident »
> parmi les faits que l'exécution produit et qui reviennent dans la boucle de mémoire
> (`fr/03_architecture.md`, § « La boucle est fermée »). Ce n'est pas une erreur à corriger :
> l'article est écrit en avance sur le code, c'est l'intention. Mais cela place **ce ticket sur
> le chemin critique de cette phrase** — soit il est livré avant la soumission, soit la phrase
> se nuance. L'écriture dans `docs/paper/article/` passe par la skill `article-verrou`.

## Ce qu'on veut

Qu'un accident survienne au hasard sur un axe pendant la journée simulée, et qu'il **coûte
du temps** aux déplacements qui l'empruntent. La probabilité de survenue doit se conditionner
à ce que la simulation sait déjà de son instant : l'heure, le jour de la semaine, la météo et
la température du bulletin, le type d'axe — et l'axe lui-même si la donnée le permet.

## Avoir un accident, subir un accident : deux populations, deux sources

C'est la distinction qui doit être posée avant tout le reste, parce qu'une bonne partie du
vocabulaire courant les confond — et le premier jet de ce ticket les confondait par endroits.

| | **Avoir** un accident | **Subir** un accident |
|---|---|---|
| De qui on parle | les personnes impliquées dans le choc | les conducteurs coincés derrière |
| Combien par événement | **2,3 usagers** (1 293 pour 561 accidents, mesuré) | des centaines, peut-être des milliers |
| Ce que ça produit | des victimes | **du retard** |
| Pour un de nos agents | **0,0025 agent par journée simulée** à 1 000 agents — il faudrait **403 674 agent-jours** pour en voir un seul | **0,6 déplacement par journée simulée** |
| La source qui le mesure | **BAAC** (`usagers`, `grav`) | le flux **DIR**, enregistrements `AbnormalTraffic` |
| Dans ce ticket | **hors périmètre** | **c'est tout le sujet** |

**Le ticket ne modélise que la colonne de droite.** Un agent n'est jamais victime : il est
ralenti par l'accident d'un autre. C'était déjà au § « hors périmètre » comme une préférence ;
c'est maintenant chiffré — à l'échelle de nos cohortes, un agent impliqué dans un accident est
un événement qu'on ne verrait jamais, et le modéliser serait du décor sans mesure possible.

### Et les données elles-mêmes séparent la cause de l'effet

Vérifié sur le flux DATEX II du 2026-09-14 : les 48 enregistrements `AbnormalTraffic` portent un
`abnormalTrafficType` explicite — **43 `queuingTraffic`** (bouchon) et **5 `slowTraffic`**
(ralentissement). La cause (`Accident`) et l'effet (`AbnormalTraffic`) sont donc deux types
d'enregistrements distincts.

⚠ **Et le lien entre les deux est rare et non garanti.** Deux instantanés le même jour :

| Sonde | Accidents | Trafics anormaux | dont regroupés avec un accident |
|---|---:|---:|---:|
| 2026-09-14, 9 h 13 | 23 | 48 (43 bouchons, 5 ralentissements) | **0** |
| 2026-09-14, ~11 h | 14 | 7 (5 bouchons, 2 ralentissements) | **1** |

L'exploitant **peut** ranger un bouchon et son accident dans la même « situation », mais il ne
le fait presque jamais. On ne peut donc pas construire dessus : le flux dit *« il y a un
accident ici »* et *« il y a un bouchon là »*, et **seulement par exception** *« ce bouchon
vient de cet accident »*.

⚠ Au passage, ces deux instantanés disent autre chose : 23 accidents puis 14 en deux heures.
**Un instantané n'est pas une mesure**, ni pour le compte ni pour la durée. Tout ce qui est
avancé sur ce flux dans ce ticket est un ordre de grandeur, et le restera jusqu'à l'archivage.

Conséquence directe sur ce qu'on peut mesurer, et ce qu'on devra supposer :

| Question | Qui y répond | Statut |
|---|---|---|
| À quelle fréquence un accident survient-il, et où ? | **BAAC** | **mesurable** |
| Combien de temps dure un bouchon, et de quelle ampleur ? | flux **DIR**, `queuingTraffic` | **mesurable**, une fois l'archivage constitué |
| Ce bouchon-ci vient-il de cet accident-là ? | l'exploitant, **par exception** (1 cas sur 7, 0 sur 48) | **hypothèse**, à déclarer |
| Un accident de gravité X produit-il un bouchon de durée Y ? | personne | **hypothèse**, à déclarer |

Autrement dit : l'archivage donnera l'**échelle** des durées de bouchon — leur médiane, leur
queue — mais pas la ventilation par gravité. Le lien gravité → durée reste ce qu'il était : une
hypothèse déclarée dans `config/accidents.yaml`, désormais **calée sur une échelle mesurée** au
lieu d'être inventée de bout en bout. C'est un progrès, pas une résolution.

## Les sources officielles, et ce qu'elles portent vraiment

### 1. BAAC / ONISR — la fréquence, et tout le conditionnement

[Bases de données annuelles des accidents corporels de la circulation routière, 2005-2024](https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024),
Ministère de l'intérieur, administré par l'**ONISR**, **Licence Ouverte**, mis à jour le
2025-12-29. Quatre CSV par millésime : `caractéristiques`, `lieux`, `véhicules`, `usagers`,
joints par l'identifiant d'accident.

C'est la source à retenir, et pour une raison précise : **son conditionnement recouvre presque
exactement ce que la simulation a déjà en main.**

| Ce que la simulation sait à l'instant du départ | Le champ BAAC qui lui répond |
|---|---|
| heure murale de GAMA (`sim_clock.wall_clock`) | `hrmn` |
| jour de la semaine (date simulée, ou date tirée par `weather_draw`) | `jour` / `mois` / `an` |
| condition météo du bulletin (`WEATHER_CODE_*`) | `atm` — 1 normale, 2 pluie légère, 3 pluie forte, 4 neige-grêle, 5 brouillard, 6 vent fort, 7 éblouissant, 8 couvert |
| précipitations du bulletin (`PRECIP_TOTAL_DAY_MM`) | `surf` — 1 normale, 2 mouillée, 3 flaques, 4 inondée, 5 enneigée, 7 verglacée |
| nuit / jour (`SUNSET`, `SUNRISE` du bulletin) | `lum` — 1 plein jour … 5 nuit avec éclairage allumé |
| type d'arête OSM (`highway`) du graphe OSMnx | `catr` — 1 autoroute, 2 nationale, 3 départementale, 4 voie communale, 7 route de métropole urbaine |
| zone de congestion du nœud (`city` / `agglo` / `outside`) | `agg` — 1 hors agglomération, 2 en agglomération |
| — | `circ`, `nbv`, `vma`, `int`, `col`, `plan`, `prof`, `infra`, `situ` |
| — | `lat` / `long` (WGS84), `dep`, `com`, `adr`, et n° de route + PR |

⚠ **Seuls les accidents CORPORELS y figurent** — définition de la source : « au moins une
victime ayant nécessité des soins ». Un accrochage matériel qui bloque une voie pendant vingt
minutes n'y est pas, et c'est pourtant le gros des perturbations. Le modèle sous-estimera donc
**structurellement** la fréquence des perturbations. Cela se dit ; cela ne se corrige pas par
un facteur de rattrapage inventé.

Et le biais n'est pas seulement de volume, il est de **nature** : ce que BAAC retient est
grave. Sur la Haute-Garonne 2024, les 561 accidents impliquent 1 293 usagers dont **52 tués**,
313 hospitalisés et 394 blessés légers ; classés par leur victime la plus grave, **9,1 % sont
mortels** et 49,9 % comptent au moins un hospitalisé. Autrement dit, **BAAC décrit la queue
lourde de la distribution des perturbations, pas son corps.** Un modèle calé dessus produira
peu d'événements, mais chacun très grave — l'inverse du profil réel d'une journée de
circulation.

### La gravité est une variable utile, pas un détail

`usagers.grav` (1 indemne, 2 tué, 3 blessé hospitalisé, 4 blessé léger) donne à chaque accident
une gravité maximale, et cette gravité **dépend de l'axe** :

| Catégorie de route | Tué | Blessé hospitalisé | Blessé léger | Part mortelle |
|---|---:|---:|---:|---:|
| Autoroute | 4 | 26 | 37 | 6 % |
| Route départementale | **29** | 114 | 46 | **15 %** |
| Voie communale | 10 | 82 | 96 | 5 % |
| Route de métropole urbaine | 7 | 53 | 49 | 6 % |

La départementale tue, la voie communale blesse légèrement. C'est la variable qui manquait pour
deux choses à la fois :

- **la durée de blocage** — un accident mortel implique constatations, relevés, parfois
  autopsie sur place : la chaussée reste fermée bien plus longtemps qu'après un accrochage avec
  un blessé léger. La gravité est donc le pont naturel entre « un accident a lieu » et « il
  coûte *tant* de minutes » ;
- **la durée du souvenir** — un agent bloqué derrière un accident mortel et un agent bloqué
  derrière une tôle froissée n'ont pas perdu le même temps, et c'est *par le temps* que la
  différence arrive en mémoire. ⚠ **La gravité elle-même ne sort jamais du moteur** : elle sert
  à tirer une durée, rien de plus (§ « la gravité ne sort jamais du moteur »).

⚠ **Base brute, non corrigée des erreurs de saisie**, et géolocalisation inégale selon les
départements : « a minima, seule la commune de l'accident est fournie ». Sur la Haute-Garonne
2024, elle est cependant renseignée à 100 % (mesuré, voir plus bas).

⚠ **Trois pièges de téléchargement**, rencontrés le 2026-09-14 : les millésimes 2021 et 2022
s'appellent `carcteristiques-<an>.csv` (faute de frappe publiée) ; le millésime 2022 nomme sa
clé `Accident_Id` au lieu de `Num_Acc` — une jointure naïve perd l'année **en silence** ; et
chaque millésime a son URL horodatée propre, à lire dans l'API data.gouv.

### 2. Toulouse Métropole — l'axe, mais daté et filtré

Le portail [data.toulouse-metropole.fr](https://data.toulouse-metropole.fr) publie sous Licence
Ouverte v2.0 deux jeux « zones d'accumulation d'accidents corporels **2008-2012** » :

| Jeu | Contenu |
|---|---|
| `zones-daccumulation-daccidents-corporels-2008-2012-segments-toulouse-metropole` | **1 286** segments, champs `id_segment`, `code_insee`, `nom_voie`, `total_2008_2012`, `geo_shape`, `geo_point_2d` — dernière mise à jour 2021-04-20 |
| `zones-d-accumulation-d-accidents-corporels-2008-2012-carrefours-toulouse-metropo` | l'équivalent aux carrefours |

C'est probablement l'« historique par axe » dont le demandeur se souvient : il est bien nommé
**par voie**, avec une géométrie. Mais trois réserves l'écartent comme source primaire de la
loi de fréquence :

- ce sont des **zones d'accumulation**, donc un sous-ensemble sélectionné sur un critère de
  concentration — pas un recensement. En faire une fréquence surestime les axes retenus et
  donne **zéro** partout ailleurs ;
- la période **2008-2012** est dépassée de plus de dix ans ;
- le périmètre est Toulouse Métropole (37 communes), quand la simulation tourne sur le
  **polygone des 453 communes** (ticket 031).

Il reste utile en **contrôle** : un modèle de fréquence par type d'axe doit retrouver, à peu
près, les axes que ce jeu signale.

**Le rapprochement par type d'axe se fait — et il ne passe même pas par ce fichier.**

*En clair :* chaque accident du fichier BAAC porte ses coordonnées GPS. Notre carte routière
(OpenStreetMap) est faite de **tronçons**, et chaque tronçon porte une **étiquette** qui dit ce
qu'il est : voie rapide, axe principal, rue résidentielle, chemin. On pose donc chaque accident
sur le tronçon le plus proche, et on lit son étiquette. On obtient directement « tant
d'accidents par an sur les tronçons de type voie rapide, tant sur les rues résidentielles » —
sans avoir besoin du fichier de Toulouse Métropole.

*Le contrôle, tout aussi simple :* le fichier BAAC dit **lui-même** sur quelle sorte de route
l'accident a eu lieu (autoroute, départementale, voie communale…). Si BAAC dit « autoroute » et
qu'on a accroché l'accident à une rue résidentielle, c'est qu'on s'est trompé de tronçon. On
compte combien de fois ça arrive, et on publie ce pourcentage — sans lui, personne ne peut
savoir si l'appariement vaut quelque chose.

#### Plus simple encore : classer par vitesse autorisée

L'idée est meilleure que l'étiquette de type, et pour une raison bête : **une vitesse est un
nombre, les deux côtés en ont un, et il n'y a aucune table de correspondance à inventer.**

- **Côté BAAC** : `vma`, la vitesse maximale autorisée au lieu et au moment de l'accident.
  Mesurée sur la Haute-Garonne 2024 — **renseignée à 99,1 %** :

  | vma | 30 | 50 | 70 | 80 | 90 | 110 | 130 |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | Accidents | 113 | **320** | 27 | 117 | 53 | 4 | 12 |

  Soit en classes : ≤ 30 → 17,7 %, 50 → 48,9 %, 70 → 4,1 %, 80-90 → 26,0 %, ≥ 100 → 2,4 %.

- **Côté graphe** : chaque arête porte déjà une vitesse — celle d'OSM (`maxspeed`) quand elle
  est renseignée, sinon celle de la table `speeds` de `config/osmnx.yaml`, indexée par type de
  voie. Il n'y a donc **aucun trou** : toute arête a une vitesse, et c'est la même grandeur que
  `vma`.

La jointure devient : `accident → classe de vitesse`, `arête → classe de vitesse`, et la loi se
lit « tant d'accidents par an sur les voies à 50, tant sur les voies à 90 ». Aucune ontologie,
aucun arbitrage sur « une départementale urbaine, c'est quoi en OSM ».

⚠ Deux réserves, petites mais à écrire. `vma` est la vitesse **au moment de l'accident** : un
chantier à 70 sur une voie à 90 sera classé à 70 — c'est plutôt une bonne chose pour nous (la
vitesse réellement pratiquée compte plus que la vitesse nominale), mais ça décale légèrement la
classe par rapport au graphe. Et la ville de Toulouse étant largement passée à 30, la frontière
30/50 bouge dans le temps : poolé sur six millésimes, on mélange deux régimes.

#### Et le dénominateur qui manque : par kilomètre de réseau

Sans comptages, on ne peut pas faire un risque par véhicule-kilomètre. Mais on peut faire mieux
qu'un compte brut, **avec ce qu'on a déjà** : le graphe connaît la **longueur** de chaque arête
et sa classe de vitesse. On obtient donc un taux d'**accidents par kilomètre de réseau et par
an, par classe de vitesse** — entièrement calculable en interne, sans source extérieure.

Ce n'est **pas** un risque par véhicule-kilomètre, et il faut le dire clairement : un kilomètre
de rocade porte infiniment plus de véhicules qu'un kilomètre de rue résidentielle, donc le taux
par kilomètre confond encore danger et fréquentation. Mais il divise par la bonne quantité au
premier ordre, il est reproductible, et il se compare d'une classe à l'autre — ce qu'un compte
brut ne permet pas du tout.

**Troisième axe gratuit** : `agg` (en / hors agglomération) dans BAAC répond exactement aux
zones de congestion déjà posées sur le graphe (`city` / `agglo` / `outside`). Deux à trois
classes, déjà alignées des deux côtés, aucune donnée à chercher.

**La recommandation, donc** : classer par **vitesse × zone**, normaliser par les **kilomètres de
réseau** de chaque classe, et garder `catr` uniquement comme contrôle de qualité de
l'appariement.

Le détail : BAAC est
géolocalisé à 100 % sur la Haute-Garonne 2024 : chaque accident s'accroche à l'arête OSM la
plus proche du graphe de production, et cette arête **porte déjà son type** (`highway` :
`motorway`, `primary`, `secondary`, `residential`, `living_street`…) — c'est ce même tag qui
donne sa vitesse à l'arête dans `config/osmnx.yaml`. La chaîne est donc directe :

```
accident BAAC (lat, long) → arête OSM la plus proche → tag highway → classe d'axe
```

Deux garde-fous, et ils ne coûtent rien :

- **`catr` sert de contrôle croisé.** La catégorie administrative déclarée par les forces de
  l'ordre (autoroute, départementale, voie communale…) doit concorder avec le tag OSM de
  l'arête retenue. Un taux de désaccord élevé signalerait un mauvais appariement — un accident
  accroché à la contre-allée plutôt qu'à la voie rapide. **Ce taux se mesure et se publie** ;
  sans lui l'appariement est une hypothèse muette.
- **L'appariement se fait sur le graphe qui sert au routage**, celui des 453 communes, pas sur
  un extrait OSM refait pour l'occasion. Sinon les arêtes touchées n'existent pas dans le graphe
  qui calcule les itinéraires, et le mécanisme est inerte — le défaut exact du cache OSMnx
  désaligné.

Le fichier Toulouse Métropole n'entre que comme **troisième contrôle** : les axes que le modèle
désigne comme les plus accidentogènes doivent ressembler, grossièrement, à ses 1 286 segments.

### 3. Le flux des DIR — les accidents SANS blessé, sur les grands axes

C'est la réponse à l'objection « sur un grand axe, les pompiers ou la police interviennent de
toute façon » : **oui, et ces interventions sont publiées.**

Les Directions interdépartementales des routes diffusent en continu
[**Événements routiers sur le réseau routier national non concédé**](https://www.data.gouv.fr/datasets/evenements-routiers-sur-le-reseau-routier-national-non-concede),
au format **DATEX II**, sous **Licence Ouverte v2.0**, via le Point d'accès national
`transport.data.gouv.fr`. Le flux contient les accidents, les obstacles, les bouchons, les
déviations et les chantiers **en cours**, avec leur type, leur position (latitude/longitude),
leur numéro de route et leurs horodatages.

**Vérifié le 2026-09-14 à 9 h 13** sur l'agrégat (`content.xml`, 4,5 Mo) : **399 situations**
ouvertes, dont **23 accidents**, et **33 événements dans la boîte toulousaine** — les routes
`A0620` (la rocade), `A0621`, `A0624`, `A0064`, `A0068`, `N0124`, `N0020` y figurent, opérées
par la **DIR Sud-Ouest**. Le terrain est donc couvert.

**Et c'est bien un ordre de grandeur différent de BAAC.** 23 accidents ouverts à un instant
donné ; par la loi de Little, si la durée moyenne d'un accident est de 2 h, cela fait ≈ 276
accidents par jour **sur le seul réseau national non concédé** — à comparer aux **149 accidents
corporels par jour en France entière, tous réseaux confondus** (BAAC 2024). Même avec une
grande incertitude sur la durée moyenne, la conclusion tient : **le flux des DIR voit une classe
d'événements bien plus fréquente que les accidents corporels.** C'est exactement la population
manquante.

**Trois limites, et elles sont sérieuses :**

- **C'est un flux, pas un historique.** `overallEndTime` est **vide tant que l'événement est
  ouvert** — vérifié : sur les 23 accidents en cours, un seul portait une heure de fin. Un
  instantané donne le début, jamais la durée. **Pour obtenir des durées, il faut interroger le
  flux régulièrement et observer les fermetures.** Personne ne publie cet historique ; il se
  constitue.
- **Aucune gravité.** Les 23 accidents portent tous le même `accidentType` : « accident ». Le
  flux dit *qu'il se passe quelque chose et où*, BAAC dit *à quel point c'était grave*. Les deux
  sources sont complémentaires, aucune ne remplace l'autre.
- **La couverture s'arrête au réseau national non concédé.** Les autoroutes **concédées** autour
  de Toulouse (A61, A62, sections d'A64 exploitées par Vinci/ASF) n'y sont pas — et Vinci
  Autoroutes ne publie en open data que ses **parkings de covoiturage**, vérifié le même jour.
  Quant au réseau urbain ordinaire, où roule l'essentiel de nos agents, il n'est pas dans le RRN
  du tout.

**Donc : extrapoler, oui, mais dans un sens précis.** Le flux DIR permettrait de mesurer, sur la
rocade toulousaine, le rapport entre événements tous types et accidents corporels, **et** la
distribution des durées. Transporter ce rapport à une rue résidentielle serait en revanche une
hypothèse, pas une mesure — et il faudrait l'écrire comme telle.

⚠ **Ce que ça coûte** : un archivage. Interroger le flux toutes les 5 minutes, filtrer la boîte
toulousaine, journaliser les ouvertures et les fermetures. Quelques semaines avant d'avoir une
distribution de durées digne de ce nom, et **rien ne commence tant que ça n'a pas commencé** —
c'est la seule tâche du ticket qui a une latence incompressible. Elle mérite donc de démarrer
en premier, avant même les décisions de conception.

### 4. Le dénominateur — ce qui manquerait pour un vrai risque par véhicule-kilomètre

Rappel du § précédent : la normalisation retenue est **par kilomètre de réseau**, calculable en
interne, et elle suffit à comparer des classes entre elles. Ce paragraphe recense ce qu'il
faudrait **en plus** pour passer du taux par kilomètre au risque par véhicule-kilomètre — donc
pour cesser de confondre danger et fréquentation.

BAAC donne un **compte**, jamais un **taux** : il n'y a pas de véhicules-kilomètres dedans. Un
compte élevé sur un axe peut signifier « dangereux » ou simplement « très fréquenté », et rien
dans la source ne tranche. Trois pistes d'exposition, par ordre d'utilité décroissante :

| Source | Ce qu'elle donne | Sa limite |
|---|---|---|
| `comptages-routiers-et-pietons-2025` (Toulouse Métropole, capteurs IoT) | **508 628** enregistrements **horaires** : `car_count`, `heavy_vehicle_count`, `bike_count`, `pedestrian_count`, `lat`/`long` | quelques points instrumentés seulement ; la période annoncée (12/08/2024 → 31/12/2024) contredit le titre « 2025 » — **à vérifier avant usage** |
| `comptages-routiers`, `comptages_tout_mode`, `comptages-directionnels-tous-vehicules` | comptages ponctuels sur une semaine, depuis 2014 | ponctuels, non continus |
| Bilans annuels de l'ONISR | des ordres de grandeur **nationaux** par type de réseau | national ≠ toulousain ; à ne pas présenter comme un taux local |

**Arbitré** : la loi s'estime **par classe de vitesse × zone × heure × jour × état météo**,
normalisée par les **kilomètres de réseau** de chaque classe — jamais par axe nommé. Un taux par
axe demanderait un dénominateur au niveau de l'arête, qui n'existe pas.

⚠ Et il faut tenir les deux choses séparées : **localiser** un accident sur un axe reste
possible et souhaitable — c'est ce que fait le tirage. **Attribuer un risque** à cet axe ne
l'est pas. Les confondre fabriquerait un classement de dangerosité qui ne serait qu'un
classement de trafic. Aucune des trois sources ci-dessus n'est donc un prérequis : elles
amélioreraient la loi, elles ne la conditionnent pas.

## Ce que la mesure du 2026-09-14 dit déjà

Trace [`2026-09-14_06-45_accidentalite_baac_haute_garonne`](../traces/2026-09-14_06-45_accidentalite_baac_haute_garonne/README.md),
script rejouable, millésimes 2019 à 2024, `dep = 31`.

**3 789 accidents corporels en six ans**, soit **1,73 par jour** sur tout le département
(809 en 2019, 561 en 2024). Le conditionnement est bien là : pointe du soir marquée (**370
accidents à 17 h** contre 55 à 3 h), vendredi le plus chargé (643) et dimanche le plus calme
(451), départementale 189 / voie communale 188 / métropole urbaine 109 / autoroute 67 sur 2024.

Et trois constats qui doivent entrer dans la conception **avant** le code :

1. **82,1 % des accidents surviennent par temps « normal », 9,3 % sous pluie légère.** Lu tel
   quel, cela dit « la pluie est sûre ». C'est faux : c'est un compte sans exposition, et
   l'essentiel des kilomètres se parcourt aussi par beau temps. Sans dénominateur, **aucun
   effet météo n'est estimable** — seulement une composition.
2. **La neige-grêle, c'est 2 accidents en six ans.** Cette modalité est inexploitable et doit
   être fusionnée, pas estimée.
3. **Les cellules sont vides.** 24 heures × 7 jours × 4 catégories de route × 3 états météo =
   2 016 cellules pour 3 789 accidents, soit **1,88 accident par cellule**. Une table de
   fréquences empiriques serait du bruit : il faut un **modèle paramétrique** à effets
   multiplicatifs (heure × jour × météo × type d'axe), estimé sur l'ensemble.

## Le fait gênant : nos agents ne roulent pas sur les routes

C'est le constat qui décide de l'architecture, et il n'est écrit nulle part aujourd'hui.

Dans GAMA, un agent en voiture ou à vélo se déplace **à vol d'oiseau** vers le point suivant
de son plan :

```gaml
// Inhabitant.gaml:54
// TODO: se déplacer le long des routes extraites des données OSM
do goto target: moving_target speed: speed;
```

et sa vitesse est calculée pour **coller à la durée planifiée** du segment :

```gaml
// Inhabitant.gaml:390
speed <- (planned_dur > 0 and car_dist > 0) ? (car_dist / planned_dur) : default_car_speed;
```

**Conséquence** : aucun agent ne « passe » sur une arête OSM côté GAMA. Poser un accident sur
une route et attendre que GAMA ralentisse ceux qui l'empruntent ne marchera pas — il n'y a
personne à ralentir. Le ralentissement ne peut venir que de la **durée planifiée**, qui est
calculée en Python.

**Le seul endroit qui connaisse les arêtes empruntées** est le routeur OSMnx, et il fait déjà
exactement le geste demandé — une modulation arête par arête selon l'heure :

```python
# trip_helper/osmnx_direct.py:606 — _congested_travel_time
for (u, _v, _k), tt in zip(gdf.index, gdf["travel_time"].to_numpy(dtype=float)):
    free_s += tt
    cong_s += tt * _zone_factor(G.nodes[u].get(NODE_ZONE_KEY), dt)
```

`_zone_factor` applique la table de congestion TomTom par (zone, jour, heure)
(`config/osmnx.yaml`, ticket 031 décision 4). **Un accident a la même forme** : un surcoût
appliqué à des arêtes désignées, dans une fenêtre de temps. C'est le point d'insertion, et il
existe déjà.

Pour les transports collectifs, c'est OTP : un accident qui retarde un bus est un autre
mécanisme, et il sort du premier lot.

## Annoncé ou subi : ce ne sont pas la même expérience

| | **(A) Annoncé** | **(B) Subi** |
|---|---|---|
| Où le retard entre | dans les options présentées à l'agent, avant décision | dans l'exécution, après décision |
| Ce que l'agent sait | il voit « voiture : 38 min » au lieu de 24 | il découvre le retard en arrivant |
| Ce qu'on mesure | la réaction à une **information trafic** | la réaction à une **expérience vécue** |
| Ce qu'il faut construire | un canal d'information dans le prompt, et la clé de cache qui va avec | un surcoût sur la durée réalisée |
| Ce qui existe déjà | rien | `on_finish_plan` compare déjà `expected_arrive_at` à l'arrivée réelle (`Inhabitant.gaml:476`), et `submit_ob_tripfeedback` verse l'observation en STM |

**Arbitré le 2026-09-14 : (B), et (B) en entier.** L'accident subi ne se réduit pas au retard —
il produit **un retard et un souvenir**, et la **gravité** module les deux (§ « la gravité est
une variable utile »). C'est cette combinaison qui intéresse l'article : un modèle tabulaire
peut représenter des minutes perdues, il ne peut rien faire d'un souvenir qui dit *ce qui*
s'est passé. (A) reste un second lot, plus coûteux qu'il n'en a l'air (voir les caches).

⚠ **Et (A) n'est pas un terrain vierge.** Le [ticket 059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md)
construit déjà un protocole à cinq conditions pour l'injection d'un événement textuel — article
brut (C2), paraphrase sans indice modal (C3), placebo (C4), et **événement encodé pour l'oracle
tabulaire** (C5 : coupure de liens OTP, dégradation d'horaires). Un accident annoncé est de cette
famille. Le lot (A), s'il voit le jour, **reprend ce protocole** au lieu d'en inventer un second ;
sa nouveauté serait seulement que l'événement est tiré par le modèle plutôt que choisi dans la
presse. Le [ticket 024](ticket_024_diversite_et_contexte.md) annonçait d'ailleurs ce chantier
comme « distinct, et il ouvre sur un autre ticket » : c'est celui-ci.

## Les caches interdisent l'injection naïve

**Le cache d'itinéraires OSMnx est adressé sans la date**, délibérément
(`osmnx_persistent_cache.make_key:55`) :

```
raw = f"{routing_version}|{jour_de_semaine}|{creneau_1h}|{mode}|{lat_from}|{lon_from}|{lat_to}|{lon_to}"
```

Une durée qui contiendrait l'accident du mardi 8 h serait donc **resservie à tous les mardis
8 h**, y compris aux runs qui n'ont pas tiré cet accident. C'est une contrainte, pas une
préférence : la violer empoisonne un cache partagé entre expériences — celles qui n'ont jamais
demandé d'accident comprises.

Symétriquement, **le cache de décisions LLM est indexé sur `data_version()`**. Si le lot (A)
voit le jour, l'accident change le prompt et doit entrer dans la clé — sinon deux agents dans
des situations différentes se partagent une décision.

### La règle retenue : un itinéraire perturbé ne se met pas en cache

Plutôt que de poser le surcoût par-dessus une durée relue en cache, la règle est plus simple à
tenir et plus juste : **quand un événement est actif sur la fenêtre demandée, l'itinéraire se
calcule à froid et ne s'écrit pas dans le cache.** Trois conséquences, toutes bonnes :

- **le cache partagé reste propre** — aucune entrée ne contient d'accident, donc aucun run qui
  n'a pas tiré cet accident ne peut hériter de son retard ;
- **le contournement redevient possible.** C'est l'avantage décisif sur le surcoût a posteriori :
  si le surcoût entre dans le poids des arêtes touchées *avant* le plus court chemin, Dijkstra
  peut **choisir un autre chemin** — exactement ce que fait un conducteur qui apprend qu'un axe
  est bloqué. Un surcoût plaqué après coup ne sait faire qu'une chose : rallonger le trajet que
  l'agent aurait pris de toute façon ;
- **le coût est borné et mesurable** : sous un régime réaliste, presque aucun itinéraire n'est
  concerné, donc presque aucun calcul à froid. Sous un régime intensifié, le nombre de calculs
  à froid devient un **compteur à journaliser** — c'est lui qui dira si le run ralentit, et de
  combien.

⚠ Deux pièges à écrire dans le code, pas seulement ici. **Le chemin de non-cache doit être le
même code que le chemin normal**, à un poids d'arête près : deux implémentations divergeraient
en silence. Et **la décision de ne pas cacher se prend avant la lecture**, pas après — un
`lookup` qui réussit puis qu'on jette a déjà coûté, et surtout une écriture qui suit un calcul
perturbé est très facile à laisser passer.

## Le retard, lui, n'est pas dans la source

BAAC ne porte **aucune durée** : ni durée d'intervention, ni durée de blocage, ni longueur de
remontée de file. Le retard causé par un accident est donc un **paramètre exogène** au sens du
[protocole du dépôt](../arch/protocole-parametre-exogene.md) : une valeur que le modèle
consomme sans la produire, qui doit porter sa `provenance`, et qu'il est interdit d'ajuster sur
un score.

Trois conséquences :

- **la source existe, mais elle se collecte** : c'est l'archivage du flux DIR (§ 3), seul endroit
  où des durées d'événements réels sur la rocade sont observables. Elle donnera l'**échelle**,
  pas la ventilation par gravité ;
- la valeur vit dans `config/accidents.yaml` **avec sa provenance**, à la manière de
  `terminal_time.yaml` ;
- tant que l'archivage n'a pas parlé, c'est une **hypothèse déclarée**, pas une mesure — et elle
  se dit comme telle, dans le fichier comme dans l'article. Ce qui n'empêche pas d'avancer : les
  autres lots se construisent dessus et la remplacent le jour venu.

### La forme retenue : la gravité, et rien d'autre

**Arbitré le 2026-09-14 : oui, on fait simple.** Le retard se déduit de la seule **gravité**, en
six nombres :

| Gravité (BAAC `grav`) | Part des accidents (31, 2024) | Durée de blocage | Ralentissement de l'axe |
|---|---:|---|---|
| Blessé léger | 41,0 % | à fixer | à fixer |
| Blessé hospitalisé | 49,9 % | à fixer | à fixer |
| Tué | 9,1 % | à fixer | à fixer |

Six valeurs, lisibles d'un coup d'œil, contestables une par une. C'est tout le modèle.

**Pourquoi c'est le bon niveau de simplicité, et pas de la paresse :**

- la gravité est **donnée par accident** dans la source, pas reconstruite ;
- elle **varie avec l'axe**, et donc elle transporte déjà une partie de l'effet « type de
  route » : la départementale tue trois fois plus que la voie communale ;
- c'est la variable qui gouverne physiquement la durée — constatations, relevés, parfois
  intervention judiciaire sur place ;
- **elle sert à fabriquer le temps de blocage**, et c'est son seul rôle (voir juste en dessous).

**Ce qu'on abandonne, et ce que ça coûte.** Le nombre de voies (`nbv` dans BAAC, `lanes` dans
OSM) apporterait de la précision — une voie bloquée sur deux n'est pas une voie sur quatre — mais
il faudrait une abaque de capacité résiduelle que **je n'ai pas vérifiée** et qui vaudrait, au
mieux, un facteur de second ordre devant l'écart entre un accident mortel et une tôle froissée.
On s'en passe, et on l'écrit : le modèle est volontairement grossier sur la géométrie de l'axe.

**Le ralentissement s'exprime sur l'échelle qui existe déjà.** La table TomTom de
`config/osmnx.yaml` dit qu'en ville la vitesse tombe de 57 km/h à vide à 37 km/h à 8 h, soit un
facteur 1,54 pour la pointe ordinaire. Un accident se dit **sur cette échelle** — « comme trois
pointes simultanées sur cette arête » — pas « +12 minutes » sorti de nulle part. Un lecteur peut
juger un facteur ; il ne peut pas juger un nombre de minutes.

**Et les six valeurs, d'où viennent-elles ?** De l'archivage du flux DIR (§ 3) : c'est
exactement ce qu'il mesure — des durées réelles d'événements réels sur la rocade. En attendant,
ce sont des **hypothèses déclarées** dans `config/accidents.yaml`, marquées comme telles, et
remplacées dès que l'archivage a de quoi parler.

### La gravité ne sort jamais du moteur : elle se convertit en minutes

**Arbitré le 2026-09-14, et ça ferme la dernière question ouverte.** Un conducteur coincé
derrière un accident **ne sait pas** s'il a fait un mort. Il sait qu'il a perdu vingt-cinq
minutes. La gravité n'a donc aucune raison d'apparaître ni dans le prompt, ni dans le souvenir :

```
gravité (interne)  →  durée de blocage  →  ralentissement de l'arête  →  minutes perdues
                                                                              ↓
                                              « bloqué 25 minutes » → STM → LTM
```

Trois bénéfices, et le troisième n'était pas cherché :

- **c'est réaliste** — c'est ce que l'usager perçoit, et rien d'autre ;
- **ça simplifie tout l'aval.** `config/accidents.yaml` se réduit à une table
  gravité → durée ; après ça, il n'y a plus que des minutes dans le système. Aucune notion
  d'accident ne circule dans le prompt, dans le cache de décisions, ni dans la mémoire ;
- **ça éteint l'objection de suggestion lexicale.** Un souvenir qui dirait « accident
  **mortel** » ferait peser le doute que le modèle réagit au mot plutôt qu'à la situation —
  c'est exactement l'objection que le ticket 059 doit neutraliser par sa condition C3
  (paraphrase sans indice modal). En ne mettant que des minutes, la question ne se pose plus.

⚠ Un point reste à décider, mais il est petit : le souvenir dit-il **pourquoi** l'agent a perdu
ces minutes (« ralentissement sur l'itinéraire ») ou seulement **combien** ? Ne rien dire du
tout rendrait le souvenir difficile à distinguer d'une simple erreur de planification. Une
formulation neutre — un ralentissement constaté, sans cause nommée — semble le bon niveau.

## Le piège de mesure, et le détail du calcul

**Le calcul, terme à terme.** Il n'a rien de subtil, et c'est voulu — chaque facteur doit
pouvoir être contesté séparément :

| | Valeur | D'où elle vient |
|---|---:|---|
| Accidents corporels par jour, Haute-Garonne | **1,73** | 3 789 accidents / 6 ans / 365, **mesuré** sur BAAC 2019-2024 |
| Déplacements retardés par accident | **500** | ⚠ **inventé**. C'est le seul terme sans source du calcul |
| → déplacements retardés par jour dans le 31 | 865 | 1,73 × 500 |
| Déplacements quotidiens du département | 4 719 000 | 1,43 M habitants × 3,30 déplacements (manifeste EMC²) |
| → part des déplacements touchés | **1,8 × 10⁻⁴** | 865 / 4 719 000 |
| Déplacements d'une journée simulée | 3 300 | 1 000 agents × 3,30 |
| → **déplacements simulés touchés** | **0,60** | 1,8 × 10⁻⁴ × 3 300 |

**Et le terme inventé ne sauve rien.** On le fait varier sur trois ordres de grandeur :

| Déplacements retardés par accident | Déplacements simulés touchés |
|---:|---:|
| 50 | 0,06 |
| 100 | 0,12 |
| 500 | 0,60 |
| 2 000 | 2,42 |
| 10 000 | 12,10 |
| 50 000 | 60,49 |

Pour toucher **5 %** des 3 300 déplacements simulés, il faudrait **136 376 déplacements
retardés par accident**. Ce n'est pas un paramètre mal choisi : **aucune valeur plausible ne
rend le régime réaliste mesurable sur une journée.** Le régime n'est donc pas un réglage à
affiner plus tard, c'est une décision à prendre maintenant.

C'est **mot pour mot le défaut que le ticket 023 a rencontré sur la météo** : sur une seule
journée simulée, le régresseur a une variance quasi nulle et un effet mesuré à zéro ne prouve
rien. `weather_draw` l'a résolu en tirant une date météo **par agent**, en ne bougeant que le
bulletin — un dispositif *ceteris paribus*.

### Les quatre régimes possibles, et ce que chacun permet de dire

**1 · Réaliste, monde partagé.** Un accident survient au bon endroit, à la bonne heure, et tous
les itinéraires qui le traversent le subissent. C'est le seul régime physiquement cohérent —
et il ne produit **rien de mesurable** : 0,6 déplacement touché. Il sert le réalisme, l'IHM,
la copie d'écran. Il ne sert **aucune** figure de l'article. Le choisir, c'est accepter de
l'écrire ainsi : *« des accidents surviennent ; nous n'en tirons aucun résultat »*.

**2 · Tirage par agent** (le remède du ticket 023). Chaque agent porte sa propre réalisation :
il traverse, ou non, un accident tiré selon la loi, sans que cela concerne les autres. La
variance revient, l'effet devient estimable à masse constante, et le dispositif reste
*ceteris paribus*.
⚠ **Le coût conceptuel est réel et il faut le nommer** : deux agents sur la même route à la
même heure ne voient plus le même monde. Pour la météo, ce coût était nul — un bulletin n'est
pas un objet, personne ne peut constater la contradiction. **Pour un accident, il ne l'est
pas tout à fait** : un accident *est* un objet situé. Il se trouve que nos agents n'interagissent
pas sur les routes (ils vont à vol d'oiseau, § plus haut), donc rien dans la simulation ne peut
révéler l'incohérence — mais c'est une limite à publier, pas un détail d'implémentation.

**3 · Régime intensifié déclaré.** La loi garde sa forme (heure, jour, météo, type d'axe) et sa
fréquence est multipliée par un facteur **k affiché partout** : dans la configuration, dans les
logs, dans la légende de chaque figure. Les résultats se lisent comme une **élasticité** — « si
les perturbations étaient k fois plus fréquentes, voilà comment le report modal se déplacerait »
— et jamais comme une prévision. C'est honnête à condition que k ne quitte jamais le texte ;
un k oublié dans une légende transforme une sensibilité en prédiction.

**4 · L'événement scénarisé** — et c'est celui qui sert l'article. On ne tire rien : on
**pose** un accident, sur un axe choisi, à une heure choisie, et on l'applique à une cohorte
définie. C'est déjà ce que fait l'étape 3a d'hystérésis (panne de métro, chute à vélo) et ce que
cadre le [ticket 059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) avec
ses cinq conditions. La puissance statistique est maîtrisée, les conditions de contrôle
existent, le protocole est déjà écrit.

### Arbitré le 2026-09-14 : le monde partagé, et rien d'autre

**Régime 1.** L'accident est un objet situé : il tombe à un endroit, à une heure, et tous les
itinéraires qui le traversent le subissent. Pas de tirage par agent, pas de fréquence gonflée.

C'est le choix cohérent, et il a un prix qu'il faut accepter en le nommant : **le tirage
aléatoire ne produira pas de résultat mesurable**. 0,6 déplacement touché par journée simulée,
et aucun réglage n'y change rien. Le tirage sert le réalisme du monde, pas les figures.

**La mesure vient du régime 4, qui est le même monde.** C'est la bonne nouvelle du choix que tu
as fait : poser un accident plutôt que le tirer **ne change rien à la physique** — même objet
situé, même monde partagé, mêmes agents qui le traversent. Seul le tirage est remplacé par un
choix. Il n'y a donc pas deux mécanismes à écrire, mais **un seul mécanisme et deux façons de
le déclencher** :

| | Déclenchement | Ce que ça sert |
|---|---|---|
| **Aléatoire** | la loi tire le lieu, l'heure, la gravité | le monde vit ; la loi est exercée ; rien à publier |
| **Posé** | on choisit le lieu, l'heure, la gravité | la mesure, la figure, le protocole du ticket 059 |

Le régime 3 (intensifié) reste en réserve pour une figure de sensibilité, et le régime 2
(tirage par agent) est **écarté** — il brisait le monde partagé, c'est précisément ce qu'on
refuse.

⚠ Dans tous les cas : **un effet mesuré à 0,0 ne vaudra pas « pas d'effet »** tant que le
nombre d'agents touchés n'est pas journalisé à côté. C'est le motif récurrent du dépôt : une
absence de mesure produit le score parfait.

## Ce qu'il faut faire

**Lot 0 — les arbitrages (faits).** Sept décisions ont été prises dans l'échange du
2026-09-14. Elles entrent telles quelles dans les lots ; plus rien ne bloque la conception.

| # | Décision | Pourquoi |
|---|---|---|
| 1 | **Accident subi**, jamais subi *et* vécu : l'agent est ralenti par l'accident d'un autre, il n'en est jamais victime | 0,0025 agent impliqué par journée simulée — hors d'atteinte de nos cohortes |
| 2 | **Retard *et* souvenir**, les deux moitiés du ticket | un modèle tabulaire sait représenter des minutes perdues, pas un souvenir |
| 3 | **Régime réaliste, monde partagé** — pas de tirage par agent | cohérence physique ; conséquence acceptée, le tirage aléatoire ne portera aucune figure, la mesure vient de l'événement **posé** |
| 4 | **Classement par vitesse autorisée × zone**, normalisé par les kilomètres de réseau | un nombre des deux côtés (`vma` renseignée à 99,1 %, toute arête porte une vitesse) ; `catr` reste un contrôle d'appariement publié |
| 5 | **Le retard ne dépend que de la gravité** : six nombres, trois niveaux, exprimés sur l'échelle TomTom | le nombre de voies est abandonné faute d'abaque vérifiée ; la gravité est donnée par accident et varie déjà avec l'axe |
| 6 | **La gravité reste interne** : elle tire une durée, seules des **minutes** sortent du moteur | un conducteur coincé ne sait pas s'il y a eu un mort ; éteint au passage l'objection de suggestion lexicale |
| 7 | **Aucun itinéraire perturbé n'est mis en cache** : calcul à froid quand un événement est actif | garde le cache partagé propre, et ouvre le **contournement** que le surcoût a posteriori interdisait |

**Lot 0 bis — l'exposition, et c'est la porte d'entrée.** Avant tout code : **combien d'agents
traversent un axe donné à une heure donnée ?** Sur une exécution archivée, compter les
itinéraires voiture qui empruntent la rocade entre 7 h et 9 h. Ce nombre décide de tout, parce
qu'il borne ce qu'on pourra dire :

| Trajets touchés | Demi-intervalle de confiance à 95 % sur un report modal de 20 % |
|---:|---:|
| 10 | ± 24,8 pt — on ne peut rien dire |
| 50 | ± 11,1 pt |
| 100 | ± 7,8 pt |
| 200 | ± 5,5 pt |
| 400 | ± 3,9 pt — on peut conclure |

**Sous ~100 trajets touchés, l'événement posé ne portera aucune figure** (c'est l'hypothèse H2
du § « ce que l'expérience doit établir », avec ses trois issues). Cette mesure coûte une heure
de travail sur des fichiers déjà là, et elle **dimensionne** le reste : cohorte, horizon, axe
visé. La faire après avoir écrit le mécanisme, ce serait construire l'instrument sans savoir ce
qu'il doit peser.

#### ✅ MESURÉ le 2026-09-14 — verdict : moins de 100, mais le levier est trois fois moins cher

Trace `2026-09-14_11-20_exposition_rocade_lot0bis` (script rejouable, 4 min). **Sept exécutions
archivées à 1 000 agents**, trajets voiture partant entre 7 h et 9 h, itinéraires recalculés sur
le graphe `drive` et testés contre les 61 arêtes taguées `ref = A 620`.

| exécution | voiture 7-9 h / journée | touchés / journée | taux *p* | demi-IC |
|---|---:|---:|---:|---:|
| 2026-08-02_18_55 | 259,5 | 68,5 | 26,4 % | ± 9,5 pt |
| 2026-08-19_14_36 | 353,0 | **100,5** | 28,5 % | ± 7,8 pt |
| 2026-08-26_17_46 | 150,0 | 27,3 | 18,2 % | ± 15,0 pt |
| 2026-08-27_17_57 | 297,5 | 51,0 | 17,1 % | ± 11,0 pt |
| 2026-08-28_09_52 | 218,5 | 38,5 | 17,6 % | ± 12,6 pt |
| 2026-09-04_01_09 | 191,0 | 38,0 | 19,9 % | ± 12,7 pt |
| 2026-09-04_16_25 | 152,0 | 20,5 | 13,5 % | ± 17,3 pt |

**Taux de traversée de l'A 620 : médiane 18,2 %, étendue 13,5 – 28,5 %.** Trajets touchés par
journée simulée : **médiane 38,5**, moyenne 49,2, étendue 20,5 – 100,5. Une exécution sur sept
franchit déjà le seuil des 100.

**→ Issue « < 100 » de H2 à 1 000 agents.** Mais la cohorte requise, elle, est bien plus basse
que l'illustration du § suivant ne le laissait craindre :

| Seuil H2 | sur la médiane | sur la moyenne | sur le meilleur run |
|---|---:|---:|---:|
| figure à intervalle large (≥ 100) | **2 597** | 2 033 | 995 |
| figure annonçable (≥ 400) | **10 390** | 8 132 | 3 980 |

Le ticket avançait « ≈ 5 700 à 29 000 agents » ; la mesure donne **≈ 2 600 et ≈ 10 400**. Ces
chiffres-là étaient une illustration explicitement non mesurée (⚠ ci-dessous), et ils étaient
pessimistes d'un facteur ~3. **Le ticket n'est donc pas hors d'atteinte : il est hors d'atteinte
à 1 000 agents.**

**Élargir l'axe ne sauve rien, et c'est chiffré :** + A 621/A 624 porte le taux de 17,1 % à
18,7 % sur `2026-08-27_17_57`, + M 980 « Rocade Arc-en-Ciel » à 19,7 %. **+ 2,6 points pour le
double d'arêtes.** La définition retenue reste l'**A 620 seule**, la plus défendable.

**Ce que la mesure vaut, et ce qu'elle ne vaut pas.** L'itinéraire est rejouable à l'identique
hors ligne : le chemin est choisi en temps LIBRE (`osmnx_direct.py:754`) et la congestion TomTom
s'applique après, sur le chemin déjà choisi (l. 787) — le tracé ne dépend ni de l'heure ni de la
table. L'origine, non journalisée, est reconstruite comme l'activité précédant la destination ;
contrôle : détour médian 1,38-1,41 sur les sept exécutions, ~97 % des trajets cohérents.

⚠ **La limite qui compte : l'extrapolation n'est pas mesurée.** L'unique exécution archivée à
plus de 1 000 agents (`2026-06-03_05_40`, 10 000 agents) est **inexploitable** — son `moves.csv`
suit un schéma antérieur, sans `ID Personne` ni `ID Activité`, donc sans O/D récupérables. Les
tailles de cohorte ci-dessus supposent la **linéarité de *p* en N**, plausible (la cohorte
reproduit les marges de l'enquête, donc la *proportion* de traversants ne devrait pas dépendre
de la taille) mais non vérifiée. **Aucune figure ne doit s'appuyer dessus avant qu'une exécution
à cohorte élargie ne la confirme.** C'est désormais le premier geste du chantier, avant le
mécanisme.

#### Est-ce représentatif ? Oui — et c'est exactement le problème

La cohorte est construite pour reproduire les marges de l'enquête : la **proportion** d'agents
qui traversent la rocade au matin doit donc être à peu près juste. Le nombre absolu, lui, ne
peut pas l'être : **1 000 agents pour ≈ 1,43 M d'habitants, c'est un échantillon à 0,07 %.**
Quel que soit le flux réel *F* sur l'axe visé pendant la pointe, on en voit `0,0007 × F`.

| Flux réel sur l'axe, 7 h-9 h | Ce que la cohorte de 1 000 en voit | Cohorte nécessaire pour 400 touchés |
|---:|---:|---:|
| 20 000 véhicules | ≈ 14 | ≈ 29 000 agents |
| 50 000 véhicules | ≈ 35 | ≈ 11 400 agents |
| 100 000 véhicules | ≈ 70 | ≈ 5 700 agents |

**Le problème n'est donc pas la fidélité, c'est la taille.** Un échantillon parfaitement fidèle
à 0,07 % donne un nombre de trajets touchés parfaitement fidèle — et parfaitement inutilisable.
C'est une contrainte d'échantillonnage, pas un défaut du modèle, et aucun réglage du mécanisme
d'accident ne la lève.

⚠ **Et les chiffres ci-dessus sont une illustration, pas une mesure** : le flux réel sur la
rocade n'a pas été vérifié ici, et le taux de traversée doit être **compté sur une exécution
archivée**, pas déduit d'un flux routier. C'est tout l'objet de ce lot.

**Les trois leviers, et leur prix :**

| Levier | Ce qu'il donne | Ce qu'il coûte |
|---|---|---|
| **Élargir la cohorte** | le seul qui augmente vraiment l'exposition | linéaire en appels LLM — une cohorte × 6 est un budget × 6 |
| **Allonger l'horizon** | plusieurs journées, donc plusieurs événements | linéaire aussi, et la mémoire n'est plus au même état d'un jour à l'autre : ce n'est plus *ceteris paribus* |
| **Choisir un axe très fréquenté à la pointe** | gratuit | borné par la réalité : on ne peut pas faire passer plus d'agents qu'il n'en passe |

Gonfler la fréquence des accidents n'est **pas** dans cette liste : ça briserait le monde
partagé qui vient d'être choisi. Si aucun des trois leviers ne suffit, la conclusion honnête est
que **l'effet ne se mesure pas à cette échelle**, et elle s'écrit.

**Lot 0 ter — vérifier qu'un retard change quoi que ce soit (hypothèse H1, la plus lourde).**
Tout l'édifice repose sur une hypothèse que **personne n'a testée** : qu'un retard vécu hier
modifie la décision de demain. La chaîne existe — observation GAMA → STM → consolidation → LTM →
récupération → prompt — mais rien ne dit qu'un souvenir de ralentissement **survit** à la
consolidation, **remonte** à la récupération, et **pèse** sur le choix.

Ça se teste **sans une ligne du mécanisme d'accident** : injecter à la main, dans la STM d'une
cohorte, un souvenir « ralentissement constaté sur l'itinéraire, 25 minutes », et comparer les
décisions du lendemain à celles d'une cohorte témoin. Quelques dizaines d'appels LLM, une
après-midi.

Les trois issues et ce qu'on en publie sont au § « ce que l'expérience doit établir », H1 —
**aucune n'est un échec**, et celle du milieu (le souvenir remonte et ne pèse pas) est même le
résultat le plus intéressant pour l'article : un agent doté d'une mémoire n'en fait pas
forcément quelque chose.

⚠ Ce lot passe **avant** l'archivage si les deux ne peuvent pas démarrer ensemble. L'archivage a
une latence, celui-ci a un verdict — et ce verdict dimensionne tout le reste.

**Lot 1 — amorcer l'archivage du flux DIR (à lancer en premier, latence incompressible).**
C'est la seule source de **durées réelles**, et elle n'existe que si on commence à la collecter.
Quelques semaines avant qu'elle parle : elle démarre avant les décisions de conception, pas après.

*Construction sommaire.* Une tâche planifiée, un fichier SQLite, une centaine de lignes :

```
toutes les 5 min :
    xml ← GET content.xml                        # ~4,5 Mo, une requête
    pour chaque situationRecord du xml :
        si hors boîte toulousaine → ignorer
        clé ← (id, version)                      # ex. 230814-001797-1, version 4
        si clé inconnue → INSERT (première_vue = maintenant, type, route, lat, lon,
                                  début_annoncé, fin_annoncée)
        sinon           → UPDATE dernière_vue = maintenant
    pour chaque événement en base non revu dans ce passage :
        marquer fermé, fin_observée = dernière_vue
```

Une table, huit colonnes.

#### À quoi sert cette table, en une phrase

**À ce que l'ampleur du traitement ne soit pas inventée.**

C'est le seul argument qui la justifie, et il suffit. Dans l'expérience qui portera une figure —
l'événement posé — **le retard *est* le traitement**. Tout l'effet mesuré, report modal ou
hystérésis, sera l'effet de *N* minutes perdues. Le premier relecteur venu demandera d'où sort
ce *N*. Sans la table, la seule réponse possible est « nous l'avons choisi », et l'expérience ne
mesure plus que la sensibilité du modèle à un nombre arbitraire.

Le reste — le facteur des accidents matériels, le profil horaire, les axes — est du bonus et du
contrôle. Si l'archivage ne donnait que la distribution des durées de bouchon, il aurait payé
sa place.

⚠ **Et à l'inverse** : dans le tirage aléatoire (régime 1), le retard ne porte aucune figure —
0,6 déplacement touché. Pour cette moitié-là du ticket, la précision de la durée est cosmétique.
Ce n'est pas une raison de s'en passer, c'en est une de **ne pas attendre la table pour
avancer** : les autres lots se construisent sur des valeurs déclarées, et l'archivage les
remplace quand il a parlé.

#### Ce que cette table voudra dire

**Une ligne = la vie d'un événement publié**, pas un accident au sens de BAAC. La grandeur
qu'elle mesure est la **durée de publication** : `dernière_vue − première_vue`, ou
`fin_annoncée − début_annoncé` quand l'exploitant l'a renseignée — rare, 1 cas sur 23 à la
sonde du 2026-09-14, donc les deux colonnes se gardent et la première sert de recours.

⚠ **La durée de publication n'est pas la durée de gêne.** L'événement apparaît quand
l'exploitant le saisit et disparaît quand il le clôt : les deux bornes ont leur retard, et rien
ne dit qu'ils sont symétriques. C'est un **proxy**, et il se nomme comme tel partout où il sert.

**Quatre choses en sortiront, et une n'en sortira pas :**

| Ce qu'on en tire | Comment | Sert à |
|---|---|---|
| La **distribution des durées de bouchon** (`queuingTraffic`) | médiane, quartiles, queue | **l'échelle du retard** — les six nombres du § « la forme retenue » |
| Le **rapport événements / accidents corporels** | compter les événements du flux, comparer à BAAC sur le même périmètre | **le facteur manquant** pour les accidents matériels que BAAC ne voit pas |
| Le **profil horaire et hebdomadaire** sur la rocade | compter par heure et par jour | **un contrôle indépendant** de la loi estimée sur BAAC. Deux sources qui se recoupent valent mieux qu'une seule qu'on croit |
| Les **axes réellement concernés** | grouper par `roadNumber` | vérifier que la loi désigne les bons axes |
| ~~Le lien accident → bouchon~~ | — | **presque rien** : l'exploitant ne les regroupe que par exception (§ « avoir / subir »). Le rapprochement systématique reste une hypothèse déclarée — à ceci près que les cas regroupés, eux, se collectent et donneront un premier échantillon |

C'est aussi la raison pour laquelle l'archivage ne remplace pas BAAC : **BAAC dit à quelle
fréquence et où, le flux dit combien de temps et à quel point.** Aucune des deux ne fait le
travail de l'autre.

⚠ **Quatre pièges, tous à écrire dans le code :**

- **la version bouge.** `situation` et `situationRecord` portent un attribut `version` qui
  s'incrémente ; dédupliquer sur l'`id` seul écraserait l'historique des mises à jour, sur
  `(id, version)` seul créerait un faux événement à chaque correction. Clé de vie =
  l'**`id`** ; la version est une colonne, pas une identité ;
- **une disparition n'est pas toujours une fermeture.** Si le flux tombe ou si la requête
  échoue, tout disparaît d'un coup. Ne marquer fermé qu'après **deux passages** consécutifs
  d'absence, et journaliser le nombre d'événements vus à chaque passage — une chute brutale
  est une panne, pas une accalmie ;
- **rien ne garantit la stabilité de l'URL** `tipi.bison-fute.gouv.fr`. Un 404 doit lever une
  `[ALARME]`, pas remplir la base de silence ;
- **la latence est le produit, pas un défaut.** Ne pas décider au bout d'une semaine que
  « ça ne donne rien » : un accident dure des heures, il en faut des centaines pour une
  distribution.

Et une précaution de périmètre : ce flux **ne couvre pas** les autoroutes concédées ni le
réseau urbain (§ 3). Ce qu'on mesurera vaut pour la rocade et les voies rapides ; l'étendre
ailleurs sera une hypothèse déclarée.

**Lot 2 — geler la donnée BAAC.** Télécharger BAAC 2019-2024, filtrer `dep = 31`, joindre
`caractéristiques` × `lieux`, apparier chaque accident géolocalisé à l'arête OSM la plus proche
du graphe de production (le pickle des 453 communes), et archiver le résultat comme ressource
datée avec sa provenance. Les trois pièges de téléchargement sont dans la trace.

**Lot 3 — la loi de fréquence.** Estimer un modèle multiplicatif (**classe de vitesse × zone**
× heure × jour × état météo) sur les six millésimes, normalisé par les **kilomètres de réseau**
de chaque classe — et écrire noir sur blanc que ce dénominateur est une longueur, pas une
exposition au trafic. Livrer `config/accidents.yaml` : chaque coefficient porte sa source, à
la manière de `terminal_time.yaml` et de `cerema_values.yaml`. **Aucun coefficient ajusté sur
un score.**

**Lot 4 — le tirage.** Fonction **pure** de `(graine, …)`, sans `random` global ni horloge,
comme `weather_draw` : deux runs identiques produisent les mêmes accidents. Sans cela, l'A/B du
protocole exogène ne mesure rien.

**Lot 5 — le surcoût, et le contournement.** Le surcoût entre dans le **poids des arêtes
touchées avant le plus court chemin**, pour que l'itinéraire puisse changer de route au lieu de
seulement s'allonger. L'itinéraire ainsi calculé **ne s'écrit pas dans le cache** (§ « la règle
retenue »). Le retard part dans `list_planned_step_duration` ; GAMA n'a rien à savoir. Et
l'agent reçoit son **souvenir**, et il ne porte que des **minutes** : un ralentissement constaté
sur son itinéraire, sa durée. Ni le mot « accident » avec sa gravité, ni rien que l'usager
n'aurait pu constater.

**Lot 6 — la trace, et l'alarme.** Compteurs : accidents tirés, arêtes touchées, itinéraires
traversant une arête touchée, agents effectivement retardés, retard cumulé et médian. Et une
`[ALARME]` sur le défaut muet qui menace ici plus qu'ailleurs : **des accidents tirés et zéro
agent touché**. Sans ce compteur, la fonctionnalité peut ne rien faire du tout sans que rien ne
le dise.

**Lot 7 — la porte de décision.** A/B apparié par le [protocole du paramètre
exogène](../arch/protocole-parametre-exogene.md) avant toute mise en production, et
signalement à l'article.

## Un cas pratique, déroulé

Rien de ce qui précède ne vaut une exécution. Voici la même mécanique sur un agent, avec des
nombres. **Les valeurs marquées ⓘ sont mesurées ; les valeurs marquées ✎ sont choisies pour
l'exemple** — ce sont précisément celles que les lots 1 et 3 doivent remplacer.

**Le décor.** Lundi 16 mars 2026, journée simulée, départ de l'horloge à 5 h ⓘ. L'agent
`387324` ⓘ habite la 1ʳᵉ couronne et travaille à Toulouse : son trajet du matin fait
**19,7 km pour 24 minutes estimées** ⓘ *(ce sont les valeurs d'un souvenir réel du dépôt,
`agent_memory_events.csv`)*. Il part à 8 h 10, arrivée prévue 8 h 34.

### Jour 1 — l'accident

**1. Le tirage.** La loi de fréquence, estimée par classe de vitesse × zone, tire un accident
pour ce lundi à 8 h 05, sur une arête à **90 km/h** en zone `agglo` — un tronçon de l'A620 vers
Les Minimes ✎ *(nom de lieu relevé dans le flux DIR)*. Les classes à 80-90 pèsent 26,0 % des
accidents du département ⓘ, la pointe de 8 h est la deuxième de la journée ⓘ.

**2. La gravité, tirée puis convertie.** Le tirage donne « blessé hospitalisé » — 49,9 % des
accidents ⓘ. La table de `config/accidents.yaml` convertit :

| Gravité tirée | Durée de blocage | Facteur sur les arêtes |
|---|---:|---:|
| blessé hospitalisé | **45 min** ✎ | **× 4** ✎ |

La gravité s'arrête ici. **Plus rien en aval ne sait qu'il y a eu un accident, ni lequel** :
il n'y a plus qu'un facteur et une fenêtre `[8 h 05 ; 8 h 50]` sur un jeu d'arêtes.

**3. L'itinéraire, recalculé et non mis en cache.** À 8 h 10, le contrôleur demande le trajet.
Un événement est actif sur la fenêtre : **calcul à froid, pas d'écriture en cache**. Sur les
19,7 km, **6 km** ✎ empruntent des arêtes touchées :

| | Vitesse effective | Temps sur ces 6 km |
|---|---:|---:|
| Sans accident, pointe de 8 h (facteur TomTom 1,54 ⓘ) | ≈ 58 km/h | **6 min 12 s** |
| Avec accident (× 4) | ≈ 15 km/h | **24 min 50 s** |

**+ 18 min 38 s.** Le trajet passe de 24 à **43 minutes**, arrivée à **8 h 53** au lieu de
8 h 34.

**4. Le contournement, s'il existe.** Comme le surcoût entre dans le **poids des arêtes avant
le plus court chemin**, Dijkstra compare : passer quand même (43 min) ou contourner par les
boulevards, 6 km de plus à 30 km/h (**31 min** ✎). Il contourne. **L'agent perd 7 minutes au
lieu de 19** — et c'est le comportement qu'on veut, celui d'un conducteur qui évite un axe
bloqué. Avec un surcoût plaqué après coup, ce choix n'existerait pas.

**5. Ce que GAMA en fait.** La durée du segment part dans `list_planned_step_duration` ; l'agent
se déplace à la vitesse qui colle à cette durée ⓘ. À l'arrivée, `on_finish_plan` compare
`CURRENT_TIMESTAMP` à `expected_arrive_at` ⓘ — le mécanisme existe déjà et journalise le retard.

**6. Le souvenir.** `submit_ob_tripfeedback` verse en STM ⓘ :

```
[ transfer ] 08:41, ralentissement constaté sur l'itinéraire, +7 min. Trajet 31 min
             au lieu de 24. Arrivée 08:41 au lieu de 08:34.
```

**Ni le mot « accident », ni la gravité, ni la cause.** Seulement ce que l'usager a pu
constater. La chaîne descendante — consolidation à 22 h, LTM, récupération — traite ce souvenir
comme les autres ⓘ.

**7. La cascade.** Le retard décale le reste de la chaîne du jour : le départ suivant se compare
à `scheduled_start_time`, et l'écart alimente `DEPARTURE_DELAY` ⓘ. Une perturbation du matin
ne s'arrête pas au premier trajet.

### Jour 2 — la décision

Même agent, même trajet, pas d'accident ce jour-là. Au moment de choisir, la récupération LTM
peut remonter le souvenir de la veille, et le prompt le présente au modèle avec les options.

**Et c'est ici que le ticket ne sait pas ce qui se passe.** Trois issues, toutes plausibles :

- le modèle **change de mode** — mais sur 19,7 km, les transports collectifs sont à ≈ 55 min
  contre 24 : le report est peu probable, et s'il a lieu il faudra se demander s'il est
  raisonnable ;
- le modèle **garde la voiture** et rien ne bouge — c'est le résultat le plus probable, et il
  se publie ;
- le modèle **garde la voiture** et le souvenir ne remonte même pas — ce n'est alors pas un
  résultat sur la mobilité, mais un défaut de la chaîne mémoire, à corriger ailleurs.

**Distinguer ces trois issues est exactement l'objet de l'expérience**, et c'est ce que le
lot 0 ter mesure pour trente appels au lieu de six semaines.

## Ce que l'expérience doit établir

Point d'honnêteté au 2026-09-14, parce qu'un ticket qui a beaucoup grossi donne une impression
de solidité que le détail ne soutient pas toujours.

**Mesuré, vérifiable, rejouable** — la trace porte les scripts :

- la source BAAC existe, ses champs sont relus un par un dans la documentation ONISR, et les
  chiffres du ticket viennent d'un script : 3 789 accidents sur six ans en Haute-Garonne,
  `vma` renseignée à 99,1 %, géolocalisation à 100 % sur 2024, 9,1 % de mortels, profil horaire
  et hebdomadaire ;
- le flux DIR existe, il est vivant, il couvre la rocade et les voies rapides toulousaines —
  sondé deux fois le même jour ;
- les trois constats de code (déplacement à vol d'oiseau, vitesse calée sur la durée planifiée,
  cache adressé sans la date) sont **lus dans le code**, lignes citées ;
- l'arithmétique d'exposition et son insensibilité au paramètre inconnu ;
- la séparation *avoir* / *subir*, chiffrée des deux côtés.

**Déclaré, pas mesuré** — et chacun doit rester marqué comme tel dans `config/accidents.yaml` :

- la relation **gravité → durée de blocage**. Aucune source. L'archivage donnera l'échelle
  globale, pas la ventilation ;
- le **facteur de ralentissement** de l'arête. Inventé, à exprimer sur l'échelle TomTom pour
  être au moins jugeable ;
- le **rapport accidents matériels / corporels**, estimé par la loi de Little sur **un seul
  instantané** — l'estimation la plus fragile du ticket, et la seconde sonde (23 → 14 accidents
  en deux heures) le montre assez ;
- les **500 déplacements retardés par accident** du calcul d'exposition, explicitement inventés.

**Non vérifié — et ce n'est pas une faiblesse du ticket, c'est son programme.** Ces trois
inconnues ne sont pas des obstacles à lever avant de commencer : **ce sont les questions
auxquelles l'expérience répond.** Elles se formulent donc comme des hypothèses testables, avec
leurs issues déclarées d'avance.

**H1 — Un retard vécu modifie la décision suivante.** L'hypothèse qui porte tout le reste.
Testée par le lot 0 ter, sans une ligne du mécanisme d'accident.

| Issue | Ce qu'on en conclut | Ce qu'on publie |
|---|---|---|
| le souvenir remonte et pèse | le dispositif produit de l'hystérésis comportementale | l'effet, son amplitude, la cohorte nécessaire |
| le souvenir remonte et ne pèse pas | **un résultat**, et il intéresse l'article : un agent LLM doté d'une mémoire n'en fait pas forcément quelque chose | le résultat nul, avec la puissance du test |
| le souvenir ne remonte pas | défaut de la chaîne mémoire, pas de la mobilité | un correctif ailleurs, et le ticket attend |

**H2 — L'exposition suffit pour conclure.** ✅ **TRANCHÉE le 2026-09-14** (trace
`2026-09-14_11-20_exposition_rocade_lot0bis`, sept exécutions archivées).

| Issue | Ce qu'on en conclut | |
|---|---|---|
| ≥ 400 trajets touchés | l'événement posé porte une figure | — |
| 100 à 400 | une figure avec un intervalle large, honnêtement annoncé | — |
| < 100 | l'effet ne se mesure pas **à cette échelle** — et ça s'écrit, avec la taille de cohorte qu'il aurait fallu | ✅ **retenue** |

**Résultat : médiane 38,5 trajets touchés par journée simulée à 1 000 agents** (étendue
20,5 – 100,5 ; taux de traversée de l'A 620 médian 18,2 %). La taille de cohorte qu'il aurait
fallu — et que l'issue retenue oblige à écrire — est de **≈ 2 600 agents** pour une figure à
intervalle large et **≈ 10 400** pour une figure annonçable, sous une hypothèse de linéarité
qui reste **à vérifier** : la seule exécution archivée à 10 000 agents est antérieure aux
identifiants de `moves.csv` et ne se joint pas. Détail au lot 0 bis.

**H3 — L'appariement accident → arête est fidèle.** Mesuré par le taux de désaccord avec
`catr`. Un taux élevé ne tue rien : il oblige à remonter d'un cran, à la commune ou à la classe
de vitesse déclarée par BAAC plutôt qu'à l'arête.

⚠ **L'ordre reste ce qu'il était**, pour une raison qui n'est plus « éviter de perdre du
temps » mais « dimensionner le dispositif » : H1 et H2 se mesurent **avant** d'écrire le
mécanisme parce que leurs réponses en fixent la taille — cohorte, horizon, axe visé. Les mesurer
après reviendrait à construire un instrument sans savoir ce qu'il doit peser.

Et une issue à ne jamais confondre avec une autre : **un effet mesuré à zéro n'est un résultat
que si le nombre d'agents touchés est publié à côté.** Sinon c'est une absence de mesure
déguisée en résultat — le motif récurrent du dépôt.

## Hors périmètre

- **Faire rouler les agents sur le graphe routier dans GAMA.** C'est le vrai remède au constat
  ci-dessus, c'est un ticket à part entière, et il est gros. Ce ticket-ci contourne, il ne
  corrige pas.
- **L'agent victime de l'accident** (blessure, trajet interrompu, sortie de la simulation).
  Chiffré : **0,0025 agent par journée simulée** à 1 000 agents, soit 403 674 agent-jours pour
  en voir un. Ce n'est pas une préférence, c'est un événement hors d'atteinte de nos cohortes.
- **Les accidents sur le réseau de transport collectif** (retard de bus, de tram, de TER) :
  autre mécanisme, côté OTP et `PublicTransport.gaml`.
- **La propagation de la congestion** — remontée de file, report sur les axes voisins,
  réaffectation dynamique en cours de trajet. Aucune de ces trois choses n'est modélisable avec
  un déplacement à vol d'oiseau.
- **Les expériences `_nosim`**, qui n'exécutent aucun trajet : un accident subi n'y a aucun
  effet, par construction. Si le lot (A) voit le jour, elles redeviennent concernées.
- **Un facteur de rattrapage des accidents matériels** absents de BAAC : la sous-estimation se
  publie, elle ne se compense pas par un chiffre inventé.

## Critères d'acceptation

- [ ] `config/accidents.yaml` existe, chaque coefficient porte sa **source** et sa
      `provenance`, et aucun n'a été ajusté sur un score.
- [ ] La ressource gelée d'accidents appariés aux arêtes est datée, tracée, et son script de
      construction se rejoue.
- [ ] Le tirage est **déterministe** : deux runs de même graine produisent le même ensemble
      d'accidents. Un test le vérifie.
- [ ] **Aucun itinéraire perturbé n'est écrit dans le cache OSMnx.** Un test vérifie qu'après
      un run avec accidents, aucune entrée de cache ne porte de durée perturbée — et que la
      décision de ne pas cacher est prise **avant** la lecture, pas après.
- [ ] Le chemin « accident actif » et le chemin normal sont **le même code**, à un poids
      d'arête près. Le nombre de calculs à froid provoqués par les accidents est journalisé.
- [ ] Le **taux de désaccord entre `catr` et le tag `highway`** de l'arête appariée est mesuré
      et publié. Un appariement sans ce taux est une hypothèse muette.
- [ ] La **gravité** de chaque accident tiré est journalisée à côté du retard produit : sans
      elle, impossible de dire si la loi de durée de blocage fait ce qu'on croit.
- [ ] Le rapport de run publie : accidents tirés, arêtes touchées, **agents effectivement
      retardés**, retard médian et cumulé, et la répartition par gravité. Une `[ALARME]` se
      lève si des accidents sont tirés et qu'aucun agent n'est touché.
- [ ] Le **souvenir** d'un agent retardé existe et se retrouve dans `agent_memory_events.csv`.
      Un accident qui produit un retard sans laisser de trace en mémoire n'a livré que la
      moitié du ticket.
- [ ] La documentation dit explicitement ce que la loi couvre : **les accidents corporels**, et
      le facteur d'extension aux accidents matériels s'il a été estimé sur le flux DIR — avec,
      dans les deux cas, le sens et l'ampleur du biais restant.
- [ ] **H1 est tranchée avant le mécanisme** : le pré-test de sensibilité mémoire (lot 0 ter) a
      eu lieu, et son résultat — y compris nul — est archivé avec la puissance du test.
- [ ] Le régime retenu (**réaliste, monde partagé**, mesure par événement posé) est écrit dans
      `docs/arch/` avec sa raison, et la limite qu'il emporte — le tirage aléatoire ne porte
      aucune figure — y figure aussi.
- [x] Le **nombre d'agents traversant l'axe visé** est mesuré et publié **avant** que le
      mécanisme soit écrit. Sous ~100 trajets touchés, aucune figure n'est annoncée.
      → Fait le 2026-09-14 : **38,5 par journée simulée** (médiane, 1 000 agents), donc
      **aucune figure n'est annoncée à cette échelle**. Trace
      `2026-09-14_11-20_exposition_rocade_lot0bis`.
- [ ] La **linéarité de l'exposition en la taille de cohorte** est vérifiée sur une exécution
      à cohorte élargie. Tant qu'elle ne l'est pas, les tailles « ≈ 2 600 / ≈ 10 400 agents »
      restent une extrapolation et ne portent aucune figure. **Premier geste du chantier.**
- [ ] L'archivage du flux DIR tourne, et ses **durées observées** ont remplacé les hypothèses de
      `config/accidents.yaml` — ou bien le fichier dit toujours, explicitement, qu'elles sont des
      hypothèses.
- [ ] L'A/B du protocole exogène est passé avant la mise en production, et son résultat est
      archivé — y compris s'il est nul.

## Questions ouvertes

*(consignées ici selon l'usage : avancer sous hypothèse, poser à la fin)*

**Tranchées le 2026-09-14** — accident subi d'abord ; classement par **vitesse autorisée ×
zone**, normalisé par les kilomètres de réseau ; pas de cache pour un itinéraire perturbé ; gravité prise en compte. Reportées dans le
lot 0.

Le **régime** est tranché lui aussi : **réaliste, monde partagé**, avec l'événement posé pour
la mesure.

La **gravité** aussi : elle reste interne et se convertit en minutes — un conducteur coincé ne
sait pas s'il y a eu un mort.

**Reste ouverte :**

1. **La base d'historique par axe** dont tu te souviens : est-ce bien les « zones
   d'accumulation 2008-2012 » de Toulouse Métropole, ou un autre fichier ? Le rapprochement par
   type d'axe n'en a pas besoin — mais un fichier plus récent et non filtré servirait de
   troisième contrôle.

## Sources

- [BAAC — bases de données annuelles des accidents corporels, 2005-2024](https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024)
  — Ministère de l'intérieur / ONISR, Licence Ouverte, maj 2025-12-29.
- [Description des bases de données annuelles](https://www.onisr.securite-routiere.gouv.fr/sites/default/files/2024-10/Description%20des%20bases%20de%20donn%C3%A9es%20annuelles.pdf)
  — ONISR, 23 octobre 2024 : définitions et modalités de chaque champ.
- [Open data de l'ONISR](https://www.onisr.securite-routiere.gouv.fr/en/data-tools/open-data)
  — bilans annuels, indicateurs labellisés.
- [Événements routiers sur le réseau routier national non concédé](https://www.data.gouv.fr/datasets/evenements-routiers-sur-le-reseau-routier-national-non-concede)
  — DIR / Bison Futé, DATEX II, Licence Ouverte v2.0, temps réel. Agrégat :
  `http://tipi.bison-fute.gouv.fr/bison-fute-ouvert/publicationsDIR/Evenementiel-DIR/grt/RRN/content.xml`
  (vérifié le 2026-09-14 : 399 situations, 23 accidents, 33 événements dans la boîte toulousaine,
  routes A0620 / A0621 / A0624 / A0064 / A0068 présentes).
- [data.toulouse-metropole.fr](https://data.toulouse-metropole.fr) — zones d'accumulation
  d'accidents corporels 2008-2012 (segments et carrefours), comptages routiers IoT et ponctuels,
  Licence Ouverte v2.0.
- [`docs/traces/2026-09-14_06-45_accidentalite_baac_haute_garonne/`](../traces/2026-09-14_06-45_accidentalite_baac_haute_garonne/README.md)
  — la mesure Haute-Garonne et son script rejouable.
- [ticket 059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) — le
  protocole à cinq conditions pour un événement injecté, que le lot (A) doit reprendre.
- [ticket 024](ticket_024_diversite_et_contexte.md), § hors périmètre — « la réaction aux
  perturbations […] ouvre sur un autre ticket ».
- [ticket 023](ticket_023_fenetre_meteo_jeux_geles.md) et
  `services/llm-agents/urban_mobility_agents/utils/weather_draw.py` — le précédent de la
  variance nulle et son remède.
- [ticket 031](ticket_031_perimetre_453_communes.md), décision 4 — la table de congestion
  TomTom par zone et par heure, dont l'accident reprend la forme.
- [`docs/arch/protocole-parametre-exogene.md`](../arch/protocole-parametre-exogene.md) — la
  porte par laquelle le retard doit passer.
- [`docs/arch/routing.md`](../arch/routing.md) — les deux moteurs, et l'horloge qu'ils reçoivent.
