# Périmètre de population — la même base des deux côtés ?

> Ticket [020](../tickets/ticket_020_perimetre_population_cerema.md). Travaux
> d'instruction, pas de correction : ce document **établit et qualifie** les écarts de
> base entre la population interrogée par l'enquête et la population simulée. Les
> corrections qui dépassent un ajustement de mesure ouvrent leurs propres tickets.
>
> Rapport grand public : [`docs/traces/2026-08-24_perimetre_population/rapport.html`](../traces/2026-08-24_perimetre_population/rapport.html).
> Mesures et tables : [`docs/traces/2026-08-24_perimetre_population/`](../traces/2026-08-24_perimetre_population/README.md).

## Le problème, en une phrase

Toute la chaîne de mesure du dépôt compare des parts modales simulées aux cibles de
[`cerema_values.yaml`](../../scripts/data/population/cerema_values.yaml) — globalement et
dans huit sous-catégories. Cette comparaison n'a de sens que si les deux côtés parlent de
la **même population** et du **même objet compté**. Ce n'était pas établi : c'était
supposé.

Un biais de périmètre est le plus en amont de la famille déjà tracée par les tickets 015,
016, 017 et 019 — *un coefficient appris sur une variable, appliqué à une autre, et
l'écart invisible dans les agrégats*. Il déplace **toutes** les cibles à la fois.

## Les trois pièces de cadrage

| Pièce | Rôle |
|---|---|
| [`population_emc2_2023.yaml`](../../scripts/data/population/population_emc2_2023.yaml) | Le **cadrage** : qui l'enquête a compté, où, quand, comment |
| [`llm_module/core/population_reference.py`](../../llm_module/core/population_reference.py) | Le **chargeur validant** — refuse un cadrage incohérent, ne replie jamais |
| [`llm_module/data/commune_couronne.json`](../../llm_module/data/commune_couronne.json) | La correspondance **commune → couronne** des 453 communes, et la géométrie des couronnes (`couronne_perimetre.geojson`) |
| [`llm_module/data/zf_couronne.json`](../../llm_module/data/zf_couronne.json) | Les **785 zones fines** avec leur secteur de tirage, leur couronne, leur code INSEE et leur commune — la ressource qui rend la couronne d'un domicile **sans géométrie au runtime** (ticket 021) |
| [`llm_module/core/residence_zone.py`](../../llm_module/core/residence_zone.py) | Le lecteur de cette table (`CouronneTable`) et la classification de référence par appartenance (`CommunalZones`), montée ici depuis l'audit pour qu'il n'en existe **qu'une** |

Le cadrage est **opposable** : chacune de ses valeurs a été recalculée depuis les
microdonnées d'enquête, et 17 tests
([`test_population_reference.py`](../../llm_module/tests/test_population_reference.py))
échouent si elle devient incohérente.

```bash
make communes-couronnes      # exige les données PROGEDO (accès restreint lil-1750)
make audit-perimetre         # les neuf axes ; codes de sortie 0 / 2 / 3
make audit-perimetre TRACE=docs/traces/<date>_perimetre   # archive le JSON

# recoupement du cadrage depuis les microdonnées (accès restreint)
llm-agents/.venv/bin/python -m scripts.data.population.audit_perimetre --recompute
```

Codes de sortie de `audit-perimetre` : **0** tout conforme, **2** au moins un axe à
corriger, **3** au moins un axe **non mesurable**. Le 3 existe parce qu'un axe non
mesuré est un axe qui passe.

## Ce que dit le cadrage, et pourquoi il ne dormait plus en commentaire

Avant ce ticket, `population_emc2_2023.yaml` était mentionné dans **un seul tableau** de
la doc d'installation, et l'essentiel de son contenu — méthodologie, échantillon,
territoire, totaux de population, découpage concentrique — dormait en commentaire. Seules
la répartition par âge, par occupation et l'équipement voiture étaient actives. C'est le
motif « vacuité » : la donnée de cadrage est là, elle a l'air d'être utilisée, elle ne
l'est pas.

Le fichier a donc été rendu actif et **recoupé en recalculant**. Résultat du recoupement,
11 grandeurs plus 4 parts de population par couronne, toutes à moins de 0,5 point :

| Grandeur | Recalculé | Cadrage |
|---|---:|---:|
| Ménages enquêtés | 10 783 | 10 783 |
| Personnes interrogées (`PENQ = 1`) | 15 775 | 15 775 |
| Déplacements recensés | 54 585 | **54 585** (et non 54 785) |
| Habitants de 5 ans et + | 1 320 k | 1 320 k |
| Ménages du territoire | 674 k | 674 k |
| Voitures par ménage (pondéré `COE0`) | 1,25 | 1,25 |
| Sans voiture / 1 voiture / 2+ | 19,4 / 45,3 / 35,3 % | 19 / 45 / 35 % |
| Déplacements internes au périmètre | 95,94 % | 95,94 % |
| Parts de population par couronne | 36,3 / 34,1 / 14,2 / 15,3 % | 36,4 / 34,1 / 14,2 / 15,4 % |

Les **parts modales cibles se reproduisent aussi** : recalculées pondérées `COEP` sur les
seuls déplacements internes, elles donnent voiture 55,0 %, marche 27,0 %, TC 12,2 %, vélo
4,2 % — contre 55 / 26 / 12 / 4 publiées. Sur *tous* les déplacements, la voiture monterait
à 56,1 %. **La cible est donc une cible intra-périmètre**, et c'est ce qui rend l'axe A4
décidable.

Deux blocs commentés **n'ont pas été rétablis**, et deux valeurs ont été corrigées :

- l'équipement vélo par type d'habitat est servi par
  [`bike_ownership.json`](../../llm_module/data/bike_ownership.json) (ticket 015), seule
  source de vérité ; une seconde copie finirait par diverger ;
- stationnement au domicile et télétravail n'ont aucun consommateur ;
- 54 785 → **54 585** déplacements recensés ;
- 68 / 109 → **69 / 108** communes en 1ʳᵉ et 2ᵉ couronne. La couche SIG de l'enquête fait
  foi contre la publication : c'est sur ses secteurs que les poids de redressement ont été
  calculés. Le total, 453, est le même.

## Les neuf axes

Mesures du 2026-08-24 sur `toulouse_population_1000.json` (1 021 personas) et le run
`2026-08-21_19_54` (3 936 trajets, 901 agents).

| Axe | Objet | Écart mesuré | Verdict |
|---|---|---|---|
| **A1** | Âge minimum | 0 persona sous 5 ans, mais aucune assertion ne le garantit | conforme |
| **A2** | Couronnes | **249 / 1 021 (24,4 %)** changent de couronne | **à corriger** |
| **A3** | Base de pondération | +0,63 en brut sur la taille de ménage, −0,07 pondéré | à publier |
| **A4** | Périmètre | **45 personas (4,4 %)** hors des 453 communes, jusqu'à 114 km | **à corriger** |
| **A5** | Fenêtre et variance | 0,0 % de trajets sous la pluie dans le run contre 44,7 % de jours pluvieux dans la fenêtre ; +5,3 °C sur le tirage des jeux gelés | à publier |
| **A6** | Jour de semaine | aucun trajet de week-end ; parts modales stables à ±1,3 pt entre jours ouvrés | conforme |
| **A7** | Objet compté | hiérarchie de mode principal inversée (**refermée le 2026-09-04**, alignée sur l'annexe p. 53 du rapport) ; reste 1,4 pt de rabattement inatteignable globalement, mais **jusqu'à 59 % de la cible TC** sur la tranche 20-50 km | hiérarchie **conforme** ; rabattement à publier → [ticket 022](../tickets/ticket_022_rabattement_mode_principal.md) |
| **A8** | Ménages | taille déclarée juste (2,10 / 2,08), **11,2 % de membres absents** | à publier |
| **A9** | Représentativité spatiale | 76,0 % réel en cœur d'agglomération contre 70,5 % cible | à publier |

### La population auditée est celle qui a tourné (2026-09-04)

`make audit-perimetre` audite désormais **la population déposée par le run**
(`<run>/population_1000.json`), et non plus un fichier du dossier `data/population/`.

Ce qui l'a rendu nécessaire, et qui était invisible : le défaut historique pointait sur
`data/population/toulouse_population_1000.json` — la sortie brute du générateur, 1 021
personas — alors que le run simulait la cohorte scellée, 1 000 personas tirés séparément. Les
deux populations n'ont **qu'un identifiant commun sur mille**. L'axe A2 joignait donc
**6 déplacements sur les 5 322** du run, et publiait un écart de **154,3 pt** calculé sur ces
six. Sur la population du run, la jointure est complète et l'écart vaut **41,2 pt**.

⚠ **Ce n'est pas un ajustement de mesure, c'est un changement d'objet.** Les neuf axes
mesuraient un fichier que personne n'avait simulé. Les verdicts publiés avant cette date sont
donc **caducs, pas « améliorés »** — en particulier A4, qui passe de « à corriger » à
« conforme » parce que la cohorte scellée n'a aucun domicile hors périmètre là où le fichier de
référence en avait un, et le code de sortie, qui passe de 2 à 0. Mesuré le 2026-09-04 sur le run
`2026-09-04_01_09` : **5 conformes, 4 à publier, code 0**.

Auditer la chaîne de génération est le travail de `control_population.py` et du scellement ;
auditer l'expérience qui a tourné est celui de ce script. `--population <fichier>` reste
disponible pour auditer une population nommée, et le script dit alors explicitement qu'il porte
peut-être sur une population que le run n'a pas simulée. Si le run n'a pas déposé sa population,
le script **s'arrête** : il ne se replie pas sur un autre fichier, puisque c'est précisément le
défaut qu'il ferme.

### A2 — Le classement en couronnes est faux, et il flatte le score

[`geo_reference.residence_zone`](../../llm_module/core/geo_reference.py) classe un domicile
par **distance à l'hypercentre** (8 / 20 / 40 km), et son commentaire annonce que « ce sont
les modalités de `lieu_residence` de la référence EMC² ». Ce n'en sont pas : l'enquête
découpe par **liste de communes** (1 / 69 / 108 / 275).

Croisement des deux classements, 1 021 personas :

| par distance ↓ / réel → | Toulouse | 1ʳᵉ | 2ᵉ | 3ᵉ | hors périmètre |
|---|---:|---:|---:|---:|---:|
| Toulouse | 376 | **66** | — | — | — |
| 1ʳᵉ couronne | — | 298 | **57** | — | — |
| 2ᵉ couronne | — | **2** | 84 | **79** | — |
| 3ᵉ couronne | — | — | — | 14 | **45** |

**L'erreur est unidirectionnelle.** Les 179 zones fines de la commune de Toulouse sont
toutes à moins de **7,0 km** de l'hypercentre : aucun Toulousain n'est classé dehors. Le
disque de 8 km, lui, mord sur Blagnac (21 personas), Balma (19), Tournefeuille (6),
Colomiers (5), Ramonville (5), L'Union (4), Aucamville (3), Launaguet (2),
Auzeville-Tolosane (1). Il **gonfle Toulouse et vide la 1ʳᵉ couronne** — où la cible
`voiture` passe de 31 % à 64 %.

Effet sur les parts modales publiées par zone, à run constant, seule la règle de
classement changeant :

| Classement | 1ʳᵉ couronne voiture | 2ᵉ marche | 3ᵉ couronne | **L1 moyen pondéré** |
|---|---:|---:|---|---:|
| par distance (publié) | 56,2 % | 20,7 % | *stratum absent* | **47,8 pt** |
| communal (correct) | 51,2 % | 16,4 % | 99 trajets | **50,7 pt** |

**Le classement erroné améliore la note de 2,9 points**, et il fait disparaître le stratum
« 3ᵉ couronne » du tableau publié.

Le risque annoncé par le ticket sur le **temps terminal** s'est en revanche largement
dissipé. Sous `tt2`, une confusion Toulouse ↔ 1ʳᵉ couronne facturait 3 + 7 min au lieu de
2 + 4, soit 4 minutes d'erreur par trajet voiture. Depuis l'alignement `tt3` du ticket 013,
les lois sont massées à zéro et les moyennes valent 0,06 à 0,52 min : la même confusion
coûte désormais **34 secondes**. Le classement reste à corriger pour la lecture ; l'urgence
côté simulation est levée.

**Refermé le 2026-09-02 par le [ticket 028](../tickets/ticket_028_temps_terminal_couronnes_communales.md).**
Les lois de temps terminal sont re-stratifiées par la table de l'enquête (`tt4`) et
`_make_travel_plan` classe ses points par appartenance aux couronnes : journal et
facturation ne peuvent plus diverger. La re-stratification rend au passage une couronne
à ~5 300 trajets d'enquête que le centroïde laissait hors strates (25,6 % → 3,9 %) — la
3ᵉ couronne passe de 409 à 3 370 trajets, et ses lois cessent de reposer sur une cellule
mince.

### A4 — Hors périmètre n'est pas une couronne

45 personas (4,4 %) habitent hors des 453 communes, entre **48 et 114 km** de l'hypercentre
(contreforts pyrénéens). Le classement métrique leur attribue « 3ᵉ couronne », parce que
« au-delà de 40 km » n'a pas de borne supérieure : ils forment **76 % de ce stratum**.

C'est le mécanisme de vacuité à l'état pur — l'absence de périmètre ne produit pas une
erreur, elle produit une classification. D'où la constante nommée
`population_reference.OUT_OF_PERIMETER`, et le test qui vérifie qu'elle n'est *pas* une
couronne.

Côté **temps terminal**, le même point recevait la loi de la 3ᵉ couronne. Depuis `tt4`
(ticket 028) il reçoit `hors périmètre`, donc la loi `default` de l'ensemble des trajets —
et il est **compté** (`terminal_time_out_of_perimeter_total`) et alarmé une fois.

Le versant destinations est en revanche négligeable : 4,5 % des lieux d'activité sont hors
périmètre, mais seulement **0,9 %** des résidents du périmètre ont une activité au-delà.
Le bassin d'emploi n'importe pas de déplacements en masse.

### A3 — L'écart fantôme de 30 %

Une cible **ménage** (`COE0`) comparée à une moyenne **personne** produit un écart qui
n'existe pas. Une population synthétique échantillonne des personnes : un ménage de 5 y
apparaît 5 fois. Pondérer chaque personne par `1/taille` rend à chaque ménage un poids
de 1 — c'est `population_reference.household_weight`, et elle a un nom pour qu'on ne la
redécouvre pas une troisième fois après le ticket 019.

| Grandeur (ménage) | Cible | Brut | Écart | Pondéré | Écart |
|---|---:|---:|---:|---:|---:|
| Personnes par ménage | 2,08 | 2,71 | **+0,63** | 2,01 | −0,07 |
| Voitures par ménage | 1,25 | 1,47 | **+0,22** | 1,23 | −0,02 |
| Sans voiture | 19 % | 13,0 % | **−6,0** | 20,7 % | +1,7 |
| 2 voitures et + | 35 % | 50,9 % | **+15,9** | 37,3 % | +2,3 |

Reste à publier, non corrigeable : les parts modales simulées sont des comptages de
déplacements non redressés, où un persona très mobile pèse plus qu'un sédentaire — ce que
le redressement d'enquête corrige et que la simulation ne corrige pas.

### A5 — Non pas une cible d'automne, mais une moyenne comparée à un point

> **Révisé le 2026-08-24** après vérification de la période de référence de l'enquête. La
> première rédaction de cet axe l'appelait « une cible d'automne, une mesure de printemps ».
> L'amplitude ne change pas ; la cause, si — et elle change ce qu'il faut faire.

**Ce que l'enquête mesure, vérifié deux fois et indépendamment.** La méthode EMC² recueille
les **déplacements de la veille** : passation du mardi au samedi hors jours fériés et
vacances scolaires, jour de référence du lundi au vendredi. Elle n'interroge personne sur
ses habitudes annuelles.
([méthodologie CEREMA](https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie))
Contrôle interne sur les dates de référence des microdonnées : seuls les mois **09 à 12 de
2022 et 01 à 02 de 2023** apparaissent — aucune observation de mars à août — et le jour de
référence est toujours ouvré (`JOUR ∈ {1..5}`, réparti 4 157 / 3 956 / 4 341 / 3 751 /
4 258). Les cibles sont donc bien des déplacements d'automne-hiver.

**Mais ce que l'enquête publie est « un jour moyen de semaine ».** La fenêtre
automne-hiver et l'exclusion des congés sont le *moyen* d'obtenir une journée ordinaire,
non une revendication saisonnière. L'écart n'est donc pas un décalage de saison : c'est un
écart de **moyennage**, et il se sépare en deux mécanismes qui n'appellent pas le même
remède.

| | Jours pluvieux | T° midi moyenne |
|---|---:|---:|
| Fenêtre d'enquête (152 j) — la cible | 44,7 % | 12,7 °C |
| Année entière (365 j) — tirage des jeux gelés | 42,5 % | **18,0 °C** |
| Jours effectivement simulés (16→20 mars) | **0,0 %** | 14,6 °C |

**(1) Les jeux gelés moyennent, mais sur la mauvaise fenêtre.** Un jour est tiré
indépendamment par décision (`sha256("<seed>:<agent_id>|<entry>") % 365`), donc la pluie y
est correctement représentée : 42,5 % contre 44,7 %, et 42,9 % des enregistrements de `v2`
portent de la précipitation. L'écart est **thermique** — 18,0 contre 12,7 °C à midi.
Restreindre le tirage à la fenêtre d'enquête corrige cet écart-là, **et lui seul**. C'est
peu coûteux et ça vaut d'être fait.

**(2) Un run ne moyenne pas.** Il rejoue des jours calendaires consécutifs réels
(`weather_loader.get_weather` apparie par mois-jour). Et sur ce point la première rédaction
était trop sévère sur deux plans :

- **thermiquement, les jours simulés sont typiques de la fenêtre d'enquête**, pas
  printaniers : 14,6 °C à midi contre 12,7 de moyenne, chaque journée tombant entre le
  **56ᵉ et le 81ᵉ centile** de la distribution de la fenêtre. Mi-mars est par ailleurs une
  semaine scolaire ordinaire, ce que la méthode cible exactement ;
- **0 % de pluie n'est pas un tirage exotique** qu'il suffirait d'éviter : **27,7 % des
  fenêtres de 5 jours consécutifs de la période d'enquête elle-même sont entièrement
  sèches** (41 sur 148). Le run n'a pas « mal tiré ».

Le grief réel est donc structurel : **une réalisation de cinq jours est comparée à une
moyenne de 152 jours**. Aucun choix de dates ne rend un run de cinq jours comparable à cette
moyenne sur le mode le plus sensible à la météo — le vélo, dont les mouvements de 4 à 5
points ont déjà arbitré les tickets 013 et 014. C'est une **limite de variance**, à publier,
et non un réglage à trouver. Les remèdes sont d'allonger l'horizon ou de tirer la météo dans
la distribution de la fenêtre au lieu de rejouer des jours consécutifs — pas de changer les
dates.

Constat de fait qui subsiste, et qui justifie de le publier : sur les 76 runs archivés
exploitables, **les 20 derniers sont tous à 0 %** d'exposition à la pluie. La chaîne de
mesure récente est donc entièrement calibrée sur des journées sèches.

⚠ **Piège d'implémentation.** La fenêtre franchit le 1er janvier. Tout filtre travaillant
en mois-jour doit tester `>= début OU <= fin`, jamais un intervalle simple — un test couvre
ce point.

### A6 — Le jour de semaine est conforme, avec deux nuances chiffrées

`no_weekend_departures` reporte tout départ de samedi ou dimanche au lundi suivant. Aucun
run courant ne l'exerce (démarrage un lundi, cinq jours au plus). Mesuré **à l'intérieur
d'EMC²** :

- les parts modales varient de **1,3 point au plus** entre les cinq jours ouvrés (voiture
  54,5 à 55,8 % ; vélo 3,7 à 4,7 %) : un run mono-journalier ne biaise pas les *parts* ;
- le lundi porte **3,16 déplacements par personne contre 3,51 le mercredi**, soit 10 % de
  volume en moins : l'écart compterait si un *volume* était comparé.

⚠ Sur un run de plus de cinq jours, le report empilerait les départs de week-end sur le
lundi et fabriquerait un lundi atypique. Non exercé aujourd'hui, à surveiller.

### A7 — L'objet compté : conforme sur la marche, hiérarchie refermée le 2026-09-04

**Ce qui est conforme.** Une ligne de `moves.csv` est un déplacement, pas une jambe (3 936
lignes, 3 936 identifiants de trajet distincts). Les jambes terminales du ticket 013
portent `is_transfer=True` et `_plan_transport_mode` ne regarde que les jambes
non-transfert. L'enquête fait de même, et c'est **vérifié dans ses microdonnées** : sur ses
39 743 déplacements détaillés, **aucun** déplacement voiture ou TC ne porte de trajet à
pied — l'accès y est une durée (`T2`/`T6`), pas un trajet. La marche n'est donc pas
surestimée par construction, ce qui était le soupçon de départ.

**Ce qui divergeait, et ne diverge plus.** La hiérarchie de mode principal était
**inversée** : `_plan_transport_mode` testait la voiture *avant* les transports collectifs,
alors que l'enquête code **760 de ses 770** déplacements mixtes voiture + TC en
« transports collectifs », et 10 seulement en « voiture » — 757 sur 767 en recomptant avec
les listes de modes complètes, cf. l'enseignement 1 ci-dessous.

**Refermé le 2026-09-04 par le [ticket 022](../tickets/ticket_022_rabattement_mode_principal.md)**,
et par la source plutôt que par une convention : le rapport publie en annexe **p. 53** la
hiérarchie complète des 36 modes enquêtés, « définie au niveau national ». L'ordre est gelé
dans [`mode_hierarchy_emc2.json`](../../llm_module/data/mode_hierarchy_emc2.json) et servi
par [`mode_hierarchy.py`](../../llm_module/core/mode_hierarchy.py) à toutes les tables du
dépôt — plus aucune cascade de `if` écrite à la main. Effet mesuré avant application :
**zéro bascule** sur les 385 888 options des jeux gelés, les 444 055 décisions en cache et
les 17 258 options du run archivé.

**Deux enseignements de méthode, tirés de la mesure.**

1. **Le rejeu de ce chiffre-ci est exact, et il révèle une inconsistance interne.** Les 770
   déplacements voiture + TC se reproduisent à l'unité (770 / 760 / 10) *à condition* de
   compter la voiture au sens large (deux-roues motorisés inclus) et une liste TC **sans le
   téléphérique ni le transport d'employeur** ; les 58 déplacements vélo + TC, eux,
   exigent la liste **complète**. Les deux chiffres d'A7 n'ont donc pas été calculés avec
   la même liste — trace du défaut du Téléo corrigé le 2026-08-26. Les deux lectures sont
   publiées dans la ressource gelée : avec les listes complètes, voiture + TC donne
   767 / 757 / 10.
2. **La hiérarchie a un cran contre-intuitif** : le **bus passe avant le train** (rangs 4
   et 8 ; 34 déplacements mixtes sur 35 codés bus). L'ordre `_BUS_MODES` avant
   `_RAIL_MODES` était donc conforme, et le constat déposé la veille — « la colonne Train
   sous-compte le rail de 62,5 % » — s'inverse. Détail :
   [`routing.md`](routing.md#la-hiérarchie-des-modes-une-seule-source).

L'effet miroir, lui, **reste entier** : la simulation ne peut structurellement pas produire
les déplacements que la cible compte en TC *parce qu'ils sont mixtes* — OTP est interrogé
mode par mode. C'est l'objet des lots 2 à 5 du ticket 022, non traités ici.

**Le chiffre global de 1,41 point (11,5 % de la cible de 12,2 %) masque l'essentiel.**
Mesuré par strate pour le [ticket 022](../tickets/ticket_022_rabattement_mode_principal.md) :

| Couronne | Cible TC | dont rabattement | **atteignable** | Part perdue |
|---|---:|---:|---:|---:|
| Toulouse | 21 % | 0,70 pt | 20,3 % | 3 % |
| 1ʳᵉ couronne | 8 % | 1,73 pt | 6,3 % | **22 %** |
| 2ᵉ couronne | 7 % | 2,19 pt | 4,8 % | **31 %** |
| 3ᵉ couronne | 6 % | 1,67 pt | 4,3 % | **28 %** |

| Distance | Cible TC | dont rabattement | **atteignable** | Part perdue |
|---|---:|---:|---:|---:|
| 2-5 km | 15 % | 0,46 pt | 14,5 % | 3 % |
| 5-10 km | 22 % | 2,83 pt | 19,2 % | 13 % |
| 10-20 km | 16 % | 6,25 pt | 9,8 % | **39 %** |
| 20-50 km | 13 % | 7,70 pt | 5,3 % | **59 %** |
| plus de 50 km | 12 % | 7,72 pt | 4,3 % | **64 %** |

Sur la tranche 20-50 km, **près de six dixièmes de la cible TC sont hors d'atteinte par
construction** — et le modèle en est « corrigé » d'autant. Ces déplacements ont une médiane
de 11,1 km contre 1,9 km pour l'ensemble ; 3,1 % des personnes mobiles en font un.

⚠ **Retirer le rabattement de la cible serait faux** : ces voyageurs se déplacent quand
même, et feront un trajet soit tout voiture soit tout TC — on ne sait pas lequel. La cible
atteignable est un **intervalle** `[cible − rabattement ; cible]`, pas un point. À corriger
**avant** d'introduire le parking-relais → [ticket 022](../tickets/ticket_022_rabattement_mode_principal.md).

#### Deux niveaux de lecture, et la table pour passer de l'un à l'autre (2026-09-04)

Le journal écrit des libellés **fins** ; la référence publie des **catégories**. L'axe rend
désormais les deux, plus la table qui les relie — de sorte que l'agrégat se **recompose**
depuis le détail au lieu d'être cru. Trace :
[`2026-09-04_10-37_modes_audit_detaille`](../traces/2026-09-04_10-37_modes_audit_detaille/README.md).

Rendu sur le run `2026-09-04_01_09`, avec 800 lignes passées en « Train », 120 en
« Deux-roues motorisé » et 37 en un libellé inventé — le run est antérieur au rail, donc
le cas se **fabrique** plutôt que de se conclure de son absence :

```
détail par libellé de mode (tel qu'écrit dans moves.csv) :
   libellé                  → catégorie                    n    part
   Marche                   marche                       586   11.0 %
   Vélo                     velo                         517    9.7 %
   Voiture Privée           voiture                     2262   42.5 %
   Transports_collectifs    transports_collectifs        479    9.0 %
   Train                    transports_collectifs        800   15.0 %
   Deux-roues motorisé      autres_modes                 120    2.3 %
   Aucun                    non_deplacement              521    9.8 %
   Trottinette partagée     libelle_inconnu               37    0.7 %
agrégé vers les 5 catégories de l'enquête : marche 12.3 % · velo 10.9 % · voiture 47.5 %
   · transports_collectifs 26.8 % · autres_modes 2.5 %
puis restreint aux 4 catégories scorées, contre la cible globale renormalisée aux mêmes 4 :
   voiture                    48.7 %  cible  56.7 %  écart  -8.0 pt
   marche                     12.6 %  cible  26.8 %  écart -14.2 pt
   transports_collectifs      27.5 %  cible  12.4 %  écart +15.2 pt
   velo                       11.1 %  cible   4.1 %  écart  +7.0 pt
hors parts modales, compté et nommé : non_deplacement 521 · libelle_inconnu 37
invariant vérifié : 5322 ligne(s) lue(s) = 5322 en détail = 5322 en catégories
```

Trois propriétés, et aucune n'est décorative.

- **Rien ne se jette.** `MOVE_MODE_MAP` n'avait que quatre entrées et pas de « Train » :
  depuis le routage du TER, un déplacement en train sortait des parts modales par un
  `continue` **muet**. Le dénominateur baissait, les parts des autres modes montaient. La
  table vit maintenant dans [`scripts/analysis/mode_labels.py`](../../scripts/analysis/mode_labels.py),
  partagée avec le carnet `selected_mode_stats` — deux copies d'une classification de
  référence divergent, et c'est précisément ce qui s'était produit.
- **Ce qui n'est pas un déplacement est compté quand même.** « Aucun » (même localisation,
  l'agent n'a pas bougé) pèse **521 lignes sur 5 322**, soit 9,8 % ; la cellule vide de
  « Plus rapide », 554. Ni l'un ni l'autre n'entre dans une part modale — mais ils sont
  nommés, comme `hors périmètre` l'est pour les couronnes depuis le ticket 021.
- **Un libellé inconnu alarme, et un libellé manquant aussi.** Hors table, il est compté
  sous `libelle_inconnu`, nommé dans l'écart de l'axe, et l'axe passe à **à corriger**
  (code de sortie 2). L'alarme s'écrit en ERROR dans l'`app.log` du run, au format que
  `make error` relit :

  ```
  2026-09-04 10:31:09 | ERROR    | scripts.analysis.mode_labels - [ALARME] 1 libellé(s) de mode hors table d'agrégation dans moves.csv · Mode de transport Choisi : « Trottinette partagée » (37) — 37/5322 ligne(s) (0.7 %) comptées en « libelle_inconnu », hors de toute part modale. Corriger scripts/analysis/mode_labels.AGGREGATION.
  ```

  Le contrôle **ne regarde pas que les données** : il confronte aussi la table à
  [`mode_hierarchy`](../../llm_module/core/mode_hierarchy.py) (ticket 022), qui décide les
  libellés du journal. Une famille de modes ajoutée en amont sans entrée dans
  l'agrégation alarme **avant** qu'un run ne la produise — c'est la seule façon d'attraper
  le prochain « Train », dont l'absence n'était visible dans aucune donnée.

**Ce que rendra le premier run avec du rail.** Une ligne de détail « Train →
transports_collectifs » à côté de la ligne « Transports_collectifs », les deux additionnées
dans l'agrégat. Aujourd'hui, 62,5 % des itinéraires portant un train portent aussi une
jambe de bus ou de car et sont donc étiquetés `Transports_collectifs` par la hiérarchie de
l'enquête (le bus passe avant le train, cf. ticket 022) : la ligne « Train » du détail
comptera le rail **pur**, et sous-comptera le rail total d'autant. C'est une propriété de
la hiérarchie, pas de l'audit, et le détail est justement ce qui la rend lisible.

#### Le même défaut, une jointure plus loin

Le compteur ajouté pour ne plus rien jeter a immédiatement trouvé son voisin :
`make audit-perimetre` **sans argument** joint la population de référence
(`toulouse_population_1000.json`, 1 021 personas) au run courant (1 000 personas) — et les
deux ne partagent **qu'un seul identifiant de personne**. Le `continue` d'origine sur
`per_person.get(...)` rendait donc un `l1_pondere = 154,3` calculé sur **6 déplacements**,
sans un mot. Avec la population du run, la jointure est à 100 % et le L1 pondéré vaut
**41,2 pt** sur les quatre couronnes.

La sous-table publie désormais son **taux de jointure**, alarme au-delà de 5 % de perte, et
se déclare **non mesurable** sous 50 % de jointure au lieu de rendre ce chiffre. Le verdict
de l'axe A2 reste celui de ses trois portes — c'est bien ce qu'il mesure — mais son écart le
dit. ⚠ **Reste une décision** : faire défaut `--population` sur la population du run
(`<run>/population_1000.json`) changerait ce que **tous** les axes mesurent, y compris les
chiffres publiés ci-dessus, et n'est donc pas un ajustement de mesure.

### A8 — La taille déclarée est juste, ce sont des membres qui manquent

547 adresses distinctes pour 1 021 personas : **419 grappes complètes**, 121 incomplètes,
4 collisions d'adresse. Taille déclarée moyenne par adresse **2,10** (cible 2,08) ; membres
réellement présents **1,87**. Il manque **11,2 %** des membres déclarés. Motif stable
selon la taille de population (7,0 % sur 10 065 personas, 11,1 % sur 1 988).

Sans effet sur les cibles de ménage, qui se lisent sur la déclaration. Avec effet réel sur
tout ce qui dépend des **co-résidents** : partage de la voiture du foyer, verrous de chaîne,
attribution de vélo — mécanisme déjà documenté par le ticket 015.

### A9 — Surconcentration, cumulative avec A2

| | Toulouse | 1ʳᵉ | 2ᵉ | 3ᵉ | cœur (T + 1ʳᵉ) |
|---|---:|---:|---:|---:|---:|
| Cible (habitants 5 ans et +) | 36,4 % | 34,1 % | 14,2 % | 15,4 % | **70,5 %** |
| Population réelle (classement communal) | 38,5 % | 37,5 % | 14,4 % | 9,5 % | **76,0 %** |
| Telle que publiée **avant le ticket 021** (classement métrique) | 43,3 % | 34,8 % | 16,2 % | 5,8 % | **78,1 %** |

La cible `voiture` valant 31 % à Toulouse contre 71–74 % dans les couronnes externes, une
surconcentration tire mécaniquement la part voiture vers le bas sans qu'aucun modèle de
choix ne soit en cause. Les deux biais **se cumulaient** : le classement métrique aggravait
la concentration publiée. Depuis les tickets 021 (journal) et 028 (temps terminal), la ligne
« publiée » n'existe plus — trait, géométrie et facturation coïncident, et l'axe A2 de
l'audit le vérifie à chaque exécution.

## Ce qui reste ouvert

- **A2 et A4 — CORRIGÉS le 2026-08-24 par le [ticket 021](../tickets/ticket_021_couronne_residence_post_traitement.md).**
  La couronne du domicile est **posée sur le persona** (`residence_zone`, avec la commune),
  lue dans le découpage par liste de communes de l'enquête ; `move_logger` la recopie et
  **n'importe plus** la fonction métrique ; `hors périmètre` est une modalité exclue des
  cibles par zone dont la masse est publiée. Aucun cache invalidé, aucun run rejoué,
  `terminal_time.yaml` intact.

  **Complétés le 2026-09-02 par le [ticket 028](../tickets/ticket_028_temps_terminal_couronnes_communales.md).**
  Le temps terminal classe lui aussi par commune et ses lois sont re-stratifiées (`tt4`) ;
  un point hors périmètre reçoit la loi `default`, compté et alarmé. Ce bump-là invalide
  le cache de plans OTP et le cache de décisions LLM — ce que le scellement de la
  population AAMAS rendait de toute façon nécessaire.

  **Ce que ça a coûté au score, mesuré à décisions constantes sur le jeu gelé `v7` sans un
  seul appel LLM** (trace [`2026-08-24_couronne_v7`](../traces/2026-08-24_couronne_v7/README.md)) :
  **+2,11 pt** de L1 par zone (41,26 → 43,38), les quatre strates dégradées et une 3ᵉ
  couronne qui **apparaît** à 41,88 là où le classement métrique n'en peuplait aucune. Le
  composite comparable, lui, ne bouge pas — `lieu_residence` n'y entre pas.

  ⚠ **Une leçon de méthode à garder.** Pondérer ce L1 par la **masse observée** rend
  −0,26 pt, soit une amélioration, alors que chaque strate empire : le reclassement sort des
  agents de Toulouse — la strate la pire — et la moyenne baisse par changement de mélange.
  Comparer deux *classements* avec des poids qui bougent avec les strates n'est pas une règle
  de score valide ; les poids publiés sont ceux du cadrage, identiques des deux côtés.

- **Aligner aussi le temps terminal sur le découpage communal** reste un ticket distinct :
  il classe des points quelconques, entre dans trois caches et exige un run complet. À
  coordonner avec la correction de calibre en attente du ticket 013.
- **A5 (moitié corrigeable) → [ticket 023](../tickets/ticket_023_fenetre_meteo_jeux_geles.md)** :
  restreindre le tirage de météo des **jeux gelés** à la fenêtre d'enquête, en gardant l'année
  pleine pour la simulation. Pré-mesuré, zéro appel LLM dépensé : **−4,90 °C** au créneau de
  départ, et **aucun effet opposable sur la pluie** (−1,20 pt contre −5,08 pt pour un simple
  re-tirage). L'autre moitié de A5 — la variance d'un run de cinq jours — **n'est pas
  corrigeable** et reste une limite à publier.
- **A7 → [ticket 022](../tickets/ticket_022_rabattement_mode_principal.md)** : aligner la
  hiérarchie sur une table mesurée dans EMC², et neutraliser la part inatteignable de la
  cible TC par un intervalle calculé sur la population (trait `rabattement_plausible`, étage
  D). Prérequis : le ticket 021, dont la couronne conditionne la propension. Produire les
  itinéraires de rabattement reste un ticket distinct et coûteux.
- **Garantir l'âge minimum par une assertion**, au lieu d'en hériter.
- **Quelle population l'audit joint-il au run ?** `make audit-perimetre` sans argument
  prend `data/population/toulouse_population_1000.json` et le run courant, qui ne
  partagent **qu'un identifiant de personne** : les parts par zone de l'axe A2 sont donc
  non mesurables par défaut (elles le disent depuis le 2026-09-04, elles ne le disaient
  pas avant). Basculer le défaut sur `<run>/population_1000.json` rendrait la jointure à
  100 % — et changerait ce que **les neuf axes** mesurent, dont tous les chiffres publiés
  ici. Décision à prendre, pas ajustement de mesure.

## Limites à publier, avec leur amplitude

Jamais en tant que « supposé négligeable » :

1. Les parts modales simulées sont des comptages non redressés ; un persona très mobile y
   pèse plus qu'un sédentaire.
2. Un run de cinq jours est une réalisation comparée à une moyenne de 152 jours : ici 0,0 %
   de trajets sous la pluie contre 44,7 % de jours pluvieux dans la fenêtre d'enquête. Ce
   n'est pas corrigeable par un choix de dates (27,7 % des fenêtres de 5 jours de la période
   d'enquête sont elles-mêmes sèches). Et le tirage des jeux gelés porte +5,3 °C de biais
   thermique, lui corrigeable en le restreignant à la fenêtre.
3. 1,41 point de la cible transports collectifs correspond à des rabattements voiture + TC
   que la simulation ne peut pas produire — **et jusqu'à 59 % de cette cible sur la tranche
   20-50 km, 31 % en 2ᵉ couronne**. La part atteignable est un intervalle, pas un point.
4. 11,2 % des membres de foyer déclarés n'existent pas comme personas.
5. La population synthétique est concentrée à 76,0 % en cœur d'agglomération contre 70,5 %
   dans le territoire enquêté.
6. **Le bassin de tirage est la Haute-Garonne, pas le périmètre d'enquête.** Les 453 communes
   de l'enquête se répartissent sur six départements ; 107 d'entre elles — dont **100 en 3ᵉ
   couronne** — sont hors du département 31 et donc **absentes** du cadre de tirage (vérifié :
   les 976 personas localisés de la population de référence sont tous en 31). Conséquence
   chiffrée, RP 2022 : le cadre Haute-Garonne plafonne la 3ᵉ couronne à **10,6 %** de la
   population quand l'enquête en compte **15,4 %** — un résidu **structurel de 4,7 points**
   sur cette strate, que ni un meilleur tirage ni un filtre plus large ne peuvent refermer.
   Le [ticket 026](../tickets/ticket_026_population_conforme_perimetre.md) ramène le L1 de
   répartition de 11,7 à ≈ 9,5 pt en remplaçant le rectangle par une liste de communes ;
   l'extension aux cinq autres départements le ramènerait à ≈ 2,7 pt. **Un `--check` vert
   après le ticket 026 ne vaudra pas conformité** : l'écart de la 3ᵉ couronne y vaut 4,8
   points pour une tolérance de 5,0.
   **Levée le 2026-09-03 (ticket 031)** : les BD TOPO 2025-03-15 et BAN des six départements sont
   dans le fork, le cadre est celui des 453 communes. Au passage, un biais du cadre par liste de
   communes a été mesuré et corrigé : les personnes du recensement à commune « undefined »
   (communes sans IRIS) étaient toutes gardées puis réparties sur les seules communes sans IRIS du
   cadre — 17 986 personnes pour 10 000 demandées et 42,5 % en 3ᵉ couronne sur les six
   départements ; en Haute-Garonne seule, +13 % sur la 3ᵉ couronne rurale, invisible. Leur poids
   est désormais multiplié par la part de la population sans IRIS du département qui vit dans le
   cadre (`data/census/filtered.py` du fork).

## Voir aussi

- [`docs/arch/score-synthesis.md`](score-synthesis.md) — usage des cibles dans le score composite
- [`docs/arch/population-post-traitements.md`](population-post-traitements.md) — traits posés à la génération
- [`docs/arch/vehicle-chain.md`](vehicle-chain.md) — chaîne de véhicules et co-résidents (A8)
- [`docs/arch/protocole-parametre-exogene.md`](protocole-parametre-exogene.md) — statut des paramètres exogènes
