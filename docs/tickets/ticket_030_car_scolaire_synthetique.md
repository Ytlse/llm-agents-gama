# Ticket 030 — Le car scolaire synthétique : rendre aux mineurs périurbains leur premier mode collectif

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ce qui suit est une **spécification**. Issu du rapport de périmètre du 2026-09-03
> (`docs/paper/population/RAPPORT_PERIMETRE_453_COMMUNES.html`, § 6 et action T7) : les GTFS
> Tisséo, TER et liO couvrent toute l'offre régulière des 453 communes, mais aucun ne porte le
> transport scolaire, qui est l'essentiel des transports collectifs des 2ᵉ et 3ᵉ couronnes.

## Le problème, en quatre mesures

1. **Le transport scolaire est le TC des couronnes externes.** Microdonnées EMC² 2023 (fichier
   déplacements × COEP, mode principal MODP) : 97 % des déplacements en autocar des habitants de
   3ᵉ couronne sont faits par des 5-17 ans pour un motif d'études (91 % en 2ᵉ, 93 % en 1ʳᵉ,
   78 % à Toulouse). L'autocar porte 65 % du TC de la 3ᵉ couronne, 57 % de la 2ᵉ ; le TER 10 %
   et 2,5 %. Sur le périmètre, le transport scolaire pèse 1,6 % de tous les déplacements, soit
   13 % du TC.
2. **Il n'est dans aucun GTFS.** Le GTFS liO (transport.data.gouv.fr, ODbL) exclut les services
   à titre principal scolaire ; ni la Région ni le Département ne publient les circuits ;
   les horaires n'existent que sur le portail d'inscription liO, circuit par circuit.
3. **Qui est concerné dans la population scellée v3** : 48 des 172 mineurs habitent sans arrêt
   Tisséo à moins de 1,5 km (18 en 2ᵉ couronne, 30 en 3ᵉ) ; 26 d'entre eux ont une activité
   d'études dans la journée, dont 16 à plus de 2 km de leur école. Sans service scolaire, leur
   part TC est nulle par construction.
4. **Les écoliers ne vont pas tous à l'école.** Dans la v3, 69 des 151 mineurs mobiles n'ont
   aucune activité d'études un lundi ; dans le vivier eqasim (11 922), 50 à 54 % des 6-17 ans
   seulement en ont une, contre 90 à 95 % dans l'EMC² un jour de semaine. Cause mesurée sur
   l'ENTD 2008 (`K_deploc.csv`) : les journées donneuses des enfants incluent les vacances
   scolaires (`V2_VAC_SCOL = 1`, 20 % des journées, 7 à 16 % d'école) et le mercredi
   (`V2_JOUR_DEP = 4`, 17 % d'école chez les 6-10 ans en 2008) ; hors vacances et hors
   mercredi, 88 à 96 % des journées donneuses ont un trajet vers l'école.

## Ce que le ticket fait

### Lot 0 — Prérequis : les écoliers vont à l'école → **ticket 031, § 1.2**
Le filtre des journées donneuses ENTD (hors vacances scolaires `V2_VAC_SCOL`, mercredi des moins
de 11 ans `V2_JOUR_DEP`) façonne la population : il est porté par le ticket 031 (construction du
fichier de population du périmètre des 453 communes), avec sa cible (≥ 88 % des 6-17 ans mobiles
avec une activité `education`) et sa ligne de contrôle. Les lots A à D ci-dessous sont du runtime
et n'en dépendent que pour avoir des écoliers à transporter.

### Lot A — Éligibilité et calcul de l'option (`llm-agents/trip_helper/`, nouveau module)
- **Éligible** : persona de 5 à 17 ans, domicile sans arrêt Tisséo à moins de 1,5 km
  (`home.public_transport = false`), trajet dont la destination (aller) ou l'origine (retour) est
  son activité `education`, école à plus de 2 km à vol d'oiseau. Le niveau vient de l'âge :
  6-10 primaire, 11-14 collège, 15-17 lycée.
- **Horaire** : un aller arrivant 5 à 15 min avant le début planifié de l'activité d'études, un
  retour partant 10 min après sa fin ; jours de classe seulement (calendrier scolaire zone C ;
  le 8 janvier 2024 de la simulation en est un). Une seule occurrence : pas de suivant.
- **Durée** : 5 min d'accès à l'arrêt + distance à vol d'oiseau × 1,5 à 20 km/h + 10 min de
  ramassage, recalée pour que la médiane retrouve les 30 min observées (EMC² : 30 min en médiane,
  20 à 40, pour 7,3 km parcourus et 4,9 km à vol d'oiseau ; détour 1,5 ; 16 km/h porte à porte).
- **Coût** : nul (transport scolaire régional gratuit depuis 2021).
- L'option porte un mode `school_bus`, compté comme transport collectif dans les métriques, les
  cibles EMC² (code 41) et l'oracle LightGBM (groupe `transit`).

### Lot B — Présentation et cycle de vie
L'option est présentée au modèle comme les autres (« car scolaire liO, gratuit, départ 7 h 25,
arrivée 8 h 05, 32 min »), avec le vélo, la marche, la voiture si disponible. Elle n'apparaît
jamais pour un adulte ni pour un trajet sans lien avec l'école. Journalisation : options
scolaires proposées / choisies par jour, compteur des éligibles sans option (école trop proche,
hors jour de classe), `[ALARME]` si un persona éligible n'en reçoit aucune sur toute la journée.
Couleur : palette TC (`green`).

### Lot C — Validation face à l'enquête
Sur les mineurs simulés des 2ᵉ et 3ᵉ couronnes, part de l'autocar dans les trajets domicile →
école par bande de distance et par niveau, face à l'EMC² : 0 à 5 % sous 1 km, 6 à 25 % entre 1
et 2 km, 29 à 45 % entre 2 et 5 km, 52 à 70 % au-delà ; 10 % au primaire, 52 % au collège,
54 % au lycée. Trace horodatée dans `docs/traces/`.

### Lot D — Si la Région livre les circuits réels
Un GTFS des circuits (arrêts, horaires, jours, établissements) remplace le calculateur du lot A
par un feed OTP, avec le même mode `school_bus` et le même filtre d'éligibilité côté runtime
(OTP proposerait le circuit aux adultes). Demande à formuler auprès de la direction des Mobilités
de la Région (antenne Haute-Garonne), sous convention de recherche ; données non personnelles.

## Ce que ce ticket ne fait pas
- Il ne modélise ni la capacité des cars ni les arrêts intermédiaires : un service porte à porte
  à horaire fixe, calibré sur les durées observées.
- Il ne distingue pas lignes régulières et circuits dédiés, que l'enquête ne sépare pas : les
  élèves qui prennent une ligne liO régulière la trouveront par OTP une fois le GTFS liO chargé.
- Il ne traite pas les TAD intercommunaux ni les navettes locales (0,02 à 0,12 % des
  déplacements, sans GTFS).

## Critères d'acceptation
1. Prérequis (ticket 031, § 1.2) livré : ≥ 88 % des 6-17 ans mobiles du vivier ont une activité
   `education`.
2. Tout persona éligible avec activité d'études un jour de classe reçoit exactement une option
   `school_bus` à l'aller et une au retour ; aucun adulte n'en reçoit.
3. Médiane des durées synthétiques sur les éligibles de la v3 (ou v4) entre 25 et 35 min.
4. Lot C exécuté sur un run complet, écarts consignés ; l'autocar compte en TC dans le rapport de
   run et dans la comparaison aux cibles.
5. Documentation : `docs/arch/routing.md` (nouvelle option), `docs/arch/controle-population-jeu-de-test.md`
   (ligne scolaires), changelog.
