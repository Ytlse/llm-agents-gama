# Ticket 013 — Temps terminal des itinéraires : la voiture et le vélo ne payent pas leur accès

Les options d'itinéraire soumises aux agents LLM facturent aux **transports collectifs**
l'intégralité de leur temps d'accès et de diffusion (marche jusqu'à l'arrêt, correspondance,
marche jusqu'à la destination), et **rien du tout** à la voiture et au vélo. Ce ticket
corrige l'asymétrie et versionne les jeux gelés qui en découlent.

**Origine** : analyse du 2026-08-17 de la campagne de calibration `ref1`. Le champion
sur-représente la voiture de **+24,7 points** sur les trajets de moins d'un kilomètre. En
remontant du symptôme aux données soumises au modèle, il apparaît que le modèle **raisonne
juste sur une réalité fausse** : on lui montre une voiture systématiquement plus rapide
qu'elle ne l'est, d'un décalage à peu près constant.

**Statut** : **implémenté le 2026-08-17** pour la chaîne de production, le rendu, les
catalogues de mutation et l'outillage de régénération. Restent à **mesurer** : le gel de
`v4` (§4.3, une commande), l'analyse de sensibilité (critère 6) et le rejeu du champion
(critère 7) — cf. §8. Bloque toujours la campagne `ref2` jusqu'au gel de `v4`.

> ### Deux corrections au ticket, établies en le mettant en œuvre
>
> **1. Le temps terminal n'était pas nul — il valait 4 min (voiture) et 2 min (vélo).**
> `_route_sync` ([osmnx_direct.py](../../llm-agents/trip_helper/osmnx_direct.py)) appliquait
> `park_base × 2` (`drive: 120`, `bike: 60`), inchangé depuis la création du fichier. Le §2
> se trompe donc sur deux points : ce n'est pas OTP mais **OSMnx** qui produit les
> itinéraires voiture et vélo (OTP ne fournit que les TC), et le stationnement *était*
> modélisé — mais fondu dans un total muet, sans provenance et sans variation par zone.
> Converti par bout de trajet (2 min et 1 min), il tombe exactement sur les valeurs
> « urbain » et « périurbain » des tables de *terminal times*. **Le défaut portait moins sur
> la magnitude que sur l'asymétrie de restitution** : les TC montrent chaque jambe, la
> voiture ne montrait rien. Conséquence pratique : le critère 4 s'applique aussi à la
> voiture — la nouvelle couche **remplace** `park_base`, elle ne s'y empile pas.
>
> **2. TROIS caches étaient aveugles au paramètre.** Le cache de décisions LLM est adressé
> par `TravelPlan.get_code()` — routes et arrêts —, donc insensible aux durées par
> construction : il aurait rejoué des décisions prises sur l'ancienne réalité **sans qu'aucun
> log ne le signale**. Le cache OTP est plus lourd encore : il ne mémorise pas des durées
> mais les **`TravelPlan` sérialisés**, options voiture et vélo comprises — un cache chaud
> aurait resservi des plans à une seule jambe portant l'ancien stationnement, soit le défaut
> de ce ticket ressuscité après sa correction. Les trois clés portent désormais
> `terminal_time.data_version()` ; la liste noire d'OTP reste non versionnée à dessein (« OTP
> ne relie pas ces deux points » ne dépend d'aucun temps terminal).

---

## 0 · Registre des décisions

### Décisions adoptées

| # | Décision | Détail |
|---|---|---|
| T1 | **C'est un défaut de données, pas de prompt** | Aucune consigne système ne sera ajoutée pour compenser. Voir §3 — c'est la décision structurante du ticket |
| T2 | Le temps terminal est un **paramètre exogène documenté**, jamais ajusté sur le score | Le calibrer sur le composite reviendrait à ajuster l'instrument pour qu'il donne la réponse attendue |
| T3 | Correction dans la **construction des scénarios**, pas dans le gabarit d'affichage | Le gabarit restitue fidèlement ce qu'OTP lui donne ; le mensonge est en amont |
| T4 | Nouveau jeu gelé **`v4`**, `v3` conservé intact | Les sections changent → toutes les évals en cache deviennent caduques. `v3` reste la trace de ce qui a produit `ref1` |
| T5 | Le vélo est traité **comme la voiture** | Sortir, déverrouiller, attacher à l'arrivée. Même nature de coût, valeur différente |
| T6 | **Analyse de sensibilité obligatoire** sur la valeur retenue | Une correction à paramètre unique non éprouvée déplacerait simplement le biais |

### Décisions écartées (et pourquoi)

| Idée | Raison du rejet |
|---|---|
| Ajouter « compte n minutes pour te garer » au prompt système | Demande au modèle de rattraper un défaut de données par arithmétique mentale. Le composite s'améliorerait, et le prompt encoderait une compensation d'un bug de pipeline — invalide dès que le pipeline est corrigé. C'est le *gaming* de la distribution dans sa forme la plus pure |
| Retirer les jambes de marche des options TC pour « rétablir la symétrie » | Symétrique mais faux des deux côtés : on perdrait une information exacte au lieu d'en ajouter une manquante |
| Ajuster la valeur du temps terminal jusqu'à ce que les parts modales collent | Ajuste l'instrument sur la cible. La cible ne doit servir qu'à mesurer, jamais à régler ce qui mesure |
| Corriger `v3` en place | Détruirait la reproductibilité de `ref1` et de son protocole pré-enregistré |
| Reporter après la publication de `ref1` | `ref1` est publiable avec sa limite déclarée (§6), mais toute campagne **suivante** sur `v3` produirait un champion dont l'acquis principal serait de compenser un bug |

---

## 1 · Le constat, mesuré

Sur les 3 009 options des jeux gelés `v3` (fichier `screen.jsonl`) :

| mode | options | décrites porte-à-porte |
|---|---|---|
| Transports collectifs | 1 479 | **100 %** |
| Marche | 977 | 48,4 % (porte-à-porte par nature) |
| Voiture | 357 | **0 %** |
| Vélo | 196 | **0 %** |

Exemple représentatif — agent `70156`, Michel-Noël, 71 ans, retraité, voiture toujours
disponible, déplacement de **1,4 km** vers un commerce :

```
- [0] foot,bus,foot: Temps de trajet : 13 minutes, dont 11 minutes de marche.
    · Marche jusqu'à 'Pradettes' : 3 minutes.
    · Bus '204' vers 'Gare SNCF Baziège' : 2 minutes.
    · Marche jusqu'à 'shop' : 8 minutes.
- [1] foot: Durée estimée : 16 minutes. Distance : 1.4 km.
- [4] bicycle: Durée estimée : 7 minutes. Distance : 1.4 km.
- [5] car: Durée estimée : 7 minutes. Distance : 1.8 km.
```

Le bus est facturé jusqu'à la dernière minute de marche, décomposée pas à pas — 11 de ses
13 minutes sont du trajet à pied. La voiture est facturée **7 minutes de conduite** : rien
pour rejoindre le véhicule, rien pour chercher une place, rien pour marcher du
stationnement au commerce. Le vélo de même.

Devant `voiture 7 / vélo 7 / bus 13 / marche 16`, **choisir la voiture est un raisonnement
correct**. Le biais mesuré n'est pas, sur ce point, un biais du modèle.

## 2 · Cause racine

`llm-agents/text_helper/templates/tpl/descriptions/travel_plan_describe_v2.j2` branche sur
la structure du plan renvoyé par OTP :

- ligne 2 — plan à **jambe unique `__DIRECT`** (voiture, vélo) → `Durée estimée : …` : la
  durée de la seule jambe ;
- ligne 3 — plan **multi-jambes** (TC) → `Temps de trajet : …, dont … de marche` : la durée
  du plan **entier**, jambes de marche comprises.

Le gabarit est fidèle à son entrée. L'asymétrie vient de ce qu'OTP renvoie les itinéraires
voiture et vélo comme un trajet de porte à porte sur le réseau, **sans modéliser le temps de
stationnement ni la marche terminale** — qui n'existent pas dans le graphe. Les jambes de
marche des plans TC, elles, sont de vraies jambes routées.

## 3 · Pourquoi ça ne se corrige pas dans le prompt

C'est la décision **T1**, et elle mérite d'être argumentée parce que la correction par le
prompt est tentante : elle est plus rapide, et elle *marcherait*.

Une consigne « prends en compte le temps de stationnement » ferait baisser la part voiture
sur les trajets courts, donc baisser le composite. Mais ce que la calibration aurait appris
n'est pas un mécanisme comportemental : c'est **« ajoute ~8 minutes aux options voiture »**,
c'est-à-dire un correctif d'un défaut précis du générateur d'itinéraires. Trois conséquences
rédhibitoires :

1. le prompt calibré **casserait** le jour où le générateur serait corrigé — il porterait une
   compensation devenue une double peine ;
2. le gain serait **présenté à tort** comme une découverte comportementale (« la calibration
   a appris que la marche compte »), alors qu'il compense une erreur de mesure ;
3. il deviendrait impossible de séparer, dans le gain d'une campagne, la part comportementale
   de la part de rattrapage d'artefact — ce qui ôte tout sens à la comparaison T1.

Le coût fixe d'accès est un mécanisme **réel** et il a sa place dans le prompt comme facteur
comportemental (hésitation, tracas, incertitude de trouver une place). Mais il ne peut y
entrer qu'une fois les durées honnêtes, faute de quoi son effet mesuré serait confondu avec
la correction du bug.

## 4 · Ce qu'il faut changer

### 4.1 Temps terminal par mode

Ajouter, à la construction des scénarios, un temps d'accès et de diffusion par mode :

| mode | composantes | ordre de grandeur à sourcer |
|---|---|---|
| voiture | rejoindre le véhicule + recherche de stationnement + marche du stationnement à la destination | à documenter, variable selon la densité (Toulouse intra-rocade vs couronnes) |
| vélo | sortir et déverrouiller + attacher à l'arrivée | nettement inférieur à la voiture |
| TC | **déjà compté** par les jambes de marche routées | aucun ajout — sinon double comptage |
| marche | nul par construction | aucun ajout |

**T2 s'applique** : la valeur vient d'une source externe (littérature mobilité, enquête EMC²,
paramètres d'un modèle de choix modal publié), elle est écrite dans un fichier de
configuration versionné avec sa provenance, et elle n'est **jamais** ajustée pour améliorer
un score. Un ordre de grandeur inventé « qui marche bien » retomberait dans le travers décrit
au §3.

Le paramètre devrait dépendre du **lieu de résidence / destination** (le stationnement n'a pas
le même coût à Toulouse intra-rocade et en 3ᵉ couronne). Une constante globale est acceptable
en première version **à condition d'être déclarée comme telle** ; la variante spatialisée est
un raffinement ultérieur.

### 4.2 Rendu

Une fois les durées corrigées, la ligne voiture et vélo doit **expliciter la décomposition**,
comme le fait déjà celle des TC — sans quoi le modèle voit un total sans comprendre d'où il
vient :

```
- [5] car: Temps de trajet : 15 minutes, dont 8 minutes d'accès et de stationnement.
    · Rejoindre le véhicule : 2 minutes.
    · Conduite : 7 minutes.
    · Stationnement et marche jusqu'à 'shop' : 6 minutes.
```

⚠️ Vérifier `calibration/evaluation.py::parse_option_modes` et `render_option_substeps` : le
mode de chaque option est lu **depuis le texte** de la ligne. Changer le format sans adapter
ces deux fonctions casserait silencieusement l'attribution des modes — donc toute la mesure.

### 4.3 Jeux gelés `v4`

- régénérer `train` / `val` / `test` / `screen` / `rank` avec les mêmes personas et le même
  découpage `sha256(agent_id) % 100` que `v3` (50/20/30) ;
- `rank` doit conserver **≥ 30 agents** (contrainte de gel du protocole §5 — `v3` est à 39,
  c'est le point le plus serré du dispositif) ;
- manifeste, effectifs, empreintes et rapport de couverture figés comme pour `v3` ;
- `v3` **conservé intact** : c'est la trace de ce qui a produit `ref1`.

### 4.4 Conséquence sur le cache

Les sections changent → `blocks_hash` inchangé mais les **décisions** changent : toutes les
évals `v3` en cache sont sans valeur pour `v4`. Une campagne sur `v4` **repart de zéro** en
budget LLM. C'est le coût réel du ticket ; il est inférieur à celui de publier une calibration
entraînée sur un instrument asymétrique.

## 5 · Critères d'acceptation

1. Sur un échantillon de `v4`, la proportion d'options **voiture et vélo décrivant un temps
   terminal** est de **100 %** (elle est de 0 % en `v3`).
2. Le total affiché d'une option voiture est **supérieur** à sa durée de conduite seule, et la
   décomposition affichée **somme** au total (pas de total incohérent avec ses sous-étapes).
3. `parse_option_modes` attribue correctement le mode sur 100 % des options du nouveau format
   (test de non-régression sur des sections `v4` réelles).
4. Aucune option TC n'a vu sa durée changer — **pas de double comptage** de la marche d'accès.
5. Le rapport de couverture `v4` est produit et `rank` ≥ 30 agents.
6. **Analyse de sensibilité (T6)** : les parts modales par tranche de distance sont recalculées
   pour au moins trois valeurs du temps terminal, et l'écart à EMC² est rapporté pour chacune.
   L'objectif n'est pas de choisir la meilleure valeur — c'est **T2** — mais de savoir si la
   conclusion dépend du réglage.
7. Le rejeu du champion de `ref1` sur `v4` est mesuré et rapporté : **quelle part des +24,7
   points de sur-représentation voiture sur `0-1km` disparaît sans toucher au prompt ?** C'est
   le chiffre qui sépare l'artefact instrumental du biais comportemental, et c'est un résultat
   publiable en soi.

## 6 · Portée scientifique — ce qui est sauvé, ce qui ne l'est pas

L'asymétrie est un **biais de mode commun** : B0, le champion, les témoins de plancher et
tous les candidats de `ref1` ont vu exactement les mêmes options.

- ✅ **T1 reste valide.** Le Δ composite test (champion − B0) est interne à un même
  instrument ; la comparaison n'est pas affectée. `ref1` est finalisable et publiable.
- ❌ **La lecture absolue tombe.** « Le modèle met les habitants en voiture pour 800 mètres »
  doit devenir « on lui a montré une voiture plus rapide qu'elle ne l'est ». À corriger dans
  le §0 et le §14 du protocole avant publication.
- ⚠️ **La mesure d'élasticité à la distance est confondue.** Le constat « la part voiture
  produite est plate (42,7 → 49,1 %) quand la réelle va de 18 % à 77 % » reste vrai, mais sa
  moitié courte est instrumentale. Le critère d'acceptation 7 est ce qui permettra de
  démêler les deux.
- 🚫 **Aucune campagne de calibration ne doit être lancée sur `v3` après ce constat.** Elle
  produirait un champion dont l'acquis principal serait de compenser ce défaut.

Question de protocole à trancher **avant** la première éval `test` sur `v4` : les personas de
`test` sont les mêmes qu'en `v3`, seules les sections changent. Est-ce un second regard sur le
même jeu (interdit par le §8), ou la première mesure d'un instrument différent ? La lecture
défendable est la seconde — le budget du §8 est **par instrument** — mais elle doit être
écrite dans un amendement daté **avant** la mesure, jamais après.

## 7 · Fichiers concernés

- `llm-agents/text_helper/templates/tpl/descriptions/travel_plan_describe_v2.j2` — rendu
- construction des scénarios / requête OTP — origine du défaut (§2)
- `prompt_calibration/calibration/evaluation.py` — `parse_option_modes`,
  `render_option_substeps` (§4.2, risque de casse silencieuse)
- `prompt_calibration/calibration_datasets/v4/` — jeux gelés + manifeste
- `prompt_calibration/PROTOCOLE.md` — amendement (§6)
- `docs/arch/prompt_calibration.md`, `docs/changelog.md`

---

## 8 · État de la mise en œuvre (2026-08-17)

### Fait

| Élément | Où | Ce qui a changé |
|---|---|---|
| Paramètre exogène documenté (T2) | `llm-agents/config/terminal_time.yaml` | Valeurs, **provenance avec liens**, libellés de rendu, grille de sensibilité. Le vélo est marqué `provenance: unsourced` — aucune référence chiffrée trouvée pour un vélo personnel |
| Source de vérité unique | `llm-agents/trip_helper/terminal_time.py` | Chargeur validant + `data_version()` pour les clés de cache. **Refuse** un temps non multiple de 60 s : c'est ce qui rend le critère 2 structurel, `floor(a + k×60) == floor(a) + k` |
| Correction en amont du gabarit (T3) | `osmnx_direct.py::_make_travel_plan` | Les plans voiture et vélo portent 3 jambes nommées (accès / trajet / diffusion). `park_s` retiré de `_route_sync` : le moteur ne rend plus que du temps réseau |
| `park_base` neutralisé, pas effacé | `llm-agents/config/osmnx.yaml` | Commenté avec l'explication : sa disparition silencieuse laisserait croire que le stationnement n'était pas modélisé |
| Rendu décomposé (§4.2) | `travel_plan_describe_v2.j2`, `travel_plan.py` | Nouvelle branche + libellé du « dont » propre au mode. **Ligne `Distance` conservée** (voir ci-dessous) |
| Étiquette de mode préservée | `models.py::TravelPlan.mode_label()` | 5 sites de production alignés. Sans ça l'étiquette devenait `"None,car,None"` et `parse_option_modes` → `categorize_mode` → la loss suivaient |
| Code de plan préservé | jambes terminales en `is_transfer=True` | `get_code()` inchangé : la clé du cache de décisions et la déduplication d'itinéraires ne bougent pas |
| Versionnage des caches | `osmnx_persistent_cache.py`, `llm/cache.py` | Les deux clés portent `data_version()` |
| Forme courte (mémoire LTM) | `travel_plan_describe_lite.j2` | Testait `legs\|length == 1` ; un plan voiture en compte 3 et serait tombé dans une branche qui n'affiche rien |
| A4 amendé (T1) | `calibration/seeding.py` | Axe `echelle` et levier `cout_fixe_vehicule` **retirés**, avec la raison conservée en commentaire. Deux tests échouent si le thème revient |
| Mode rapide (§4.3) | `scripts/prompt_base/build.py`, `make prompt-base` | Régénère la base de prompts depuis la population + OTP + OSMnx, **zéro appel LLM** |
| Consommation par la calibration | `calibration/datasets.py --entries` | Même chaîne aval ; le manifeste enregistre la source (`entries_source`) et ses limites |
| Amendement protocole (§6) | `prompt_calibration/PROTOCOLE.md` § A5 | Tranche la question du §8 : le budget est **par instrument**, `v4` en est un nouveau |
| Documentation | `docs/arch/prompt_calibration.md` §3.3, `docs/arch/cache-memory.md`, `docs/changelog.md` | |

### Tests

`llm-agents/tests/test_terminal_time.py` (40 cas) et
`prompt_calibration/calibration/tests/test_terminal_time_sections.py` (8) +
`test_datasets_entries_direct.py` (5). Suites complètes vertes : **213** côté `llm-agents`,
**1 054** côté `prompt_calibration`.

Critères d'acceptation couverts par les tests : **1** (100 % des options voiture/vélo
décrivent leur temps terminal), **2** (total > durée de conduite, et total = somme des
sous-étapes — éprouvé sur une grille de durées non alignées sur la minute), **3**
(`parse_option_modes` sur des sections au nouveau format, sous-étapes non comptées comme
options), **4** (rendu TC identique au caractère, contre une chaîne recopiée d'avant le
ticket).

### Un piège trouvé en cours de route, à ne pas défaire

La branche multi-jambes du gabarit n'affiche **pas** de distance — les options TC n'en ont
pas. Or `dist_km` d'un record est le **minimum des distances affichées dans la section**
(`metadata.extract_min_distance_km`), et sur `v3` **579 records (13,5 %)** ne la tiennent que
des lignes voiture/vélo. Aligner ces lignes sur le format TC leur aurait fait perdre
`dist_cat`, donc leur contribution à la strate distance du composite : **un score qui
s'améliore parce qu'on mesure moins**. La ligne `Distance` est donc conservée en fin
d'en-tête, et un test le verrouille — y compris sur le cas d'une section sans option de
marche directe.

### Reste à faire — ce sont des mesures, pas du code

1. **Geler `v4`** (§4.3) : `make prompt-base` puis `calibration.datasets --entries … v4`.
   Vérifier `rank ≥ 30` (le garde refuse le gel sinon) et le rapport de couverture.
2. **Critère 6 — sensibilité (T6)** : évaluer le champion sur les trois variantes de
   `terminal_time.yaml` (`low` / `central` / `high`, déjà écrites) et rapporter les parts
   modales par tranche + l'écart à EMC² pour chacune. `apply_variant()` suffixe
   `data_version()`, donc les trois jeux ne partagent aucune clé de cache. Coût : `screen` =
   569 décisions, `eval_batch_max: 8`, `eval_rpm: 12` → ~72 requêtes et ~6 min par éval,
   soit ~20 min de LLM pour les trois.
3. **Critère 7 — rejeu du champion `ref1` sur `v4`** : quelle part des +24,7 points de
   sur-représentation voiture sur `0-1km` disparaît **sans toucher au prompt** ? C'est le
   chiffre qui sépare l'artefact instrumental du biais comportemental.
4. **Corriger la lecture absolue** dans les §0 et §14 du protocole avant publication de
   `ref1` (A5 en pose le texte, la réécriture des sections reste à faire).
5. **Variante spatialisée** du temps terminal (§4.1) — raffinement ultérieur ; la constante
   globale est déclarée comme telle dans la configuration (`spatialise: false`).

---

## 9 · Ce que le premier lancement a appris (2026-08-17)

Le générateur du mode rapide a été lancé, arrêté, corrigé et relancé. Les défauts trouvés
valent d'être écrits : deux relèvent du déploiement, un est un troisième cache aveugle que
seule l'exécution a révélé.

**Les réplicas `osmnx` cuisent leur code dans l'image mais montent `config/` depuis l'hôte.**
Modifier `osmnx.yaml` sans reconstruire casse le service au démarrage
(`KeyError: 'park_base'`), tandis que le `controller` — qui monte tout `./llm-agents` — ne
voit rien. Panne visible d'un seul côté. Avertissement ajouté dans `osmnx.yaml` :
`docker compose build osmnx1` après toute modification de ce fichier.

**Le générateur n'initialisait aucun cache persistant.** Le chemin de production appelle
`init_persistent_cache` (OSMnx) et `init_otp_persistent_cache` (OTP) avec un sous-dossier par
population ; l'omission faisait recalculer chaque route à froid — **0,4 trajet/s contre 325/s
à chaud**, mesuré — et surtout ne réchauffait rien, alors que réchauffer est un bénéfice
gratuit de ce mode : il calcule exactement les routes dont un run ultérieur aura besoin. Le
manifeste de base porte désormais les taux de hit des deux caches.

**Et c'est en réparant ça que le troisième cache aveugle est apparu** — voir l'encadré en
tête de ticket. L'omission du cache dans le générateur masquait le défaut ; il aurait frappé
au premier vrai run après la correction.

**Deux erreurs de câblage du helper.** `CachedTripHelper` appartient au mode SOLARI et change
la stratégie de recherche (il passe un `max_transfers` qu'`OTPTripHelper` n'accepte pas :
100 % des routages en échec). En mode OTP la production câble `OtpCachedTripHelper`. Le
générateur appelle désormais **`init_static_data()`**, la fabrique de production, plutôt que
de reproduire ce choix — même principe que pour les prédicats de véhicule.

**Un job long doit être observable.** La première version n'écrivait qu'à la fin et ses
`print` n'étaient pas flushés : une heure sans aucun signe, indistinguable d'un plantage, et
tout perdu à l'interruption. Progression flushée toutes les 100 entrées avec débit, reste
estimé et taux de cache ; écriture incrémentale dans un `.partial`, réécrite en fin de course
dans l'ordre canonique d'énumération — dont dépend le rang d'entrée du tirage météo.

**La population source est celle de `ref1`.** `experiments/current` avait été rotaté par le
controller au démarrage (lien vers un dossier vide) — le motif « ne jamais citer un dossier
volatil ». La population a été reprise dans les archives :
`experiments/archive/2026-07-31_15_45/population_1000.json`, empreinte `d7e3e7b7…`, celle que
le manifeste de `v2` déclare comme source. `v4` conserve donc les personas de `v3`, ce que
demandait le §4.3 — la réserve sur un changement de population tombe.
