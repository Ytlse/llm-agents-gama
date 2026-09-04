# Feed GTFS annuel

Comment on obtient une offre de transport en commun couvrant les 365 jours de
l'année à partir d'exports d'opérateur qui n'en couvrent qu'une fraction.

---

## Le problème

Tisséo publie des exports « glissants » : chacun couvre environ 35 jours, et
n'est complet que sur ses premières semaines. Au-delà, l'opérateur ne publie plus
que les lignes structurantes — le nombre de lignes actives s'effondre de 123 à 3
(métro A, B, TELEO), puis à 1.

Trois pièges en découlent, tous mesurés sur les exports 2026 :

| Piège | Ce qu'il produit |
|---|---|
| **Queue tronquée** | Reprendre les dernières journées d'un export fait tourner la simulation sur un réseau réduit au métro, sans aucun signal d'erreur |
| **Recouvrement** | Deux exports décrivent une même date différemment (le 04/05/2026 : 12 538 et 12 484 trips, 11 282 en commun) ; leur union en fabrique 13 740 |
| **`trip_id` instable** | L'indice de Jaccard entre les trips d'un mardi de mars et ceux d'un mardi de septembre vaut **0.00** — les exports utilisent des espaces de noms disjoints |

Le feed qui était en service avant ce chantier souffrait des deux premiers : il
servait **13 250** trips le 08/04/2026 là où ses deux sources en donnent 12 652 et
12 660 (**+4,7 %**), et 5 438 le 12/04 contre 4 646 et 4 886 (**+11,3 %**). Sa
shape `14846` comptait 524 points issus de deux tracés différents, entrelacés par
une déduplication sur `(shape_id, shape_pt_sequence)` — un tracé chimère dont le
`shape_dist_traveled` ne correspondait plus aux arrêts.

La date de simulation elle-même n'était pas indemne. Le 16/03/2026, le feed en
service sert les 12 608 bonnes courses, mais **six d'entre elles portent une
géométrie chimère** (`14848` : 524 points contre 523 dans l'export d'origine) —
d'où une empreinte d'offre différente à nombre de courses égal. Le feed annuel
restitue l'export à l'identique :

```
feed annuel produit : 12608 trips  empreinte 649f20b34c3688cd66b61a8a
archive mars_avril  : 12608 trips  empreinte 649f20b34c3688cd66b61a8a
feed en production  : 12608 trips  empreinte a2244e86dce3975ee67d2333   ← diverge
```

---

## Ce que produit le pipeline

```
make gtfs-year          # Tisséo + TER + liO, 2026 et 2027
```

Six feeds sous `data/gtfs_year/`, plus une trace de build sous
`docs/traces/<date>_gtfs_annee/` :

| Feed | Journées réelles | Extrapolées | Sans service | Trips | Services |
|---|---|---|---|---|---|
| `tisseo_2026` | 167 | 197 | 1 | 75 008 | 8 812 |
| `tisseo_2027` | 0 | 364 | 1 | 74 688 | 8 289 |
| `ter_2026` | 181 | 184 | 0 | 1 137 | 351 |
| `ter_2027` | 0 | 365 | 0 | 1 101 | 328 |
| `lio_2026` | 133 | 232 | 0 | 6 647 | 224 |
| `lio_2027` | 0 | 365 | 0 | 6 647 | 223 |

2027 n'a aucune donnée réelle : c'est 2026 reporté par similarité de saison,
avec le calendrier scolaire et les jours fériés propres à 2027. Pour liO, cela
vaut depuis la coupe de la **falaise de lignes** du 2026-09-04 (règle 1) : la
fenêtre fiable de son export s'arrête au 11/12/2026, donc rien de 2027 n'y est
réel. Deux journées liO sur trois portent la même offre dans les deux feeds —
c'est le même export qui les nourrit.

**Chaque journée porte soit l'offre réellement publiée par l'opérateur, soit la
copie verbatim d'une journée réelle de même signature.** Aucun horaire n'est
synthétisé, aucune fréquence n'est interpolée : ce qui est servi un 15 décembre
a été publié par Tisséo, seulement pas ce jour-là.

---

## Les sept règles

### 1. Couper la queue tronquée

Une journée est écartée quand son nombre de lignes actives tombe sous 50 % du
maximum atteint par le **même type de jour** dans l'export, ou sous 15 % du
maximum de l'export tous types de jour confondus.

Le premier seuil est relatif au type de jour parce qu'un dimanche a légitimement
trois fois moins de lignes qu'un mardi : un seuil absolu exigeant rejetterait le
samedi 11/04 (88 lignes) et le dimanche 12/04 (48), qui sont des journées
normales. Le second est le filet : la règle par type de jour est aveugle quand un
type de jour n'apparaît jamais complet dans l'export — sa référence vaut alors le
niveau de la queue, et rien n'est coupé. Un export livré tardivement passerait
intact en injectant des journées réduites au métro. Ce cas est couvert par un
test.

Et la coupe cherche le plus long **suffixe** entièrement sous le seuil, pas le
premier creux : la troncature court jusqu'à la fin de l'export, alors qu'un jour
férié est un creux isolé suivi d'un retour à la normale. Couper au premier creux
amputerait l'export de mars de six journées valides, à cause du lundi de Pâques.

#### La falaise de lignes — quand l'offre globale tient et que des lignes disparaissent

Les deux seuils ci-dessus cherchent un **effondrement global**. Ils sont aveugles à
la troncature *par ligne*, celle d'un export qui décrit le réseau entier jusqu'au
prochain changement de service puis ne prolonge que les lignes dont le calendrier
était déjà renseigné.

Mesuré sur l'export liO du 2026-09-04 (2026-08-01 → 2027-08-31) : **treize lignes
`.liO 31` cessent le 11 ou le 12/12/2026** et ne reprennent jamais sur les
trente-sept semaines suivantes. Leurs 45 services ont un `end_date` compris entre le
06 et le 12/12, quand celui des quarante autres lignes de l'agence court jusqu'au
31/08/2027 : c'est l'**horizon de l'export**, arrêté au changement de service SNCF du
dimanche 13 décembre, pas une décision d'exploitation — et aucune ligne de
remplacement n'apparaît au printemps. Pendant ce temps l'offre globale perd 3 %
(4 303 → 4 165 courses le lundi) et garde **94 % de ses lignes**.

**Dix des treize desservent le périmètre d'étude, et ce sont toutes des rabattements
sur gare** : Muret, Carbonne, Noé, Villefranche, Castelnau-d'Estrétefonds, Boussens.
Sans la coupe, la journée simulée du 16 mars 2026 recevait un donneur amputé de ces
dix lignes — **3 494 courses au lieu de 4 303**.

Ce qui sépare une falaise d'une fin de saison n'est pas la forme de la perte, c'est
**ce que l'export fait ensuite**. Les cinquante-deux lignes scolaires qui s'arrêtent
le 30/06/2027 ne reprennent pas davantage, mais l'export s'achève neuf semaines plus
tard, en vacances d'été : leur absence est expliquée. D'où le critère : une saison
dure au plus dix semaines, donc si l'export couvre encore **treize semaines** après la
perte, la saison ne l'explique plus. Le contrôle coupe alors juste après la plus
précoce des pertes de la fenêtre, journalise et lève une `[ALARME]` nommant le nombre
de lignes et la couverture restante.

Lignes perdues par fenêtre de sept jours sur l'export liO, hors des 28 derniers jours :

| Date | Lignes perdues | Part du max actif | Couverture restante | Verdict |
|---|---:|---:|---:|---|
| avant le 01/12/2026 | ≤ 4 | ≤ 1,4 % | — | saisonnier, sous le plancher |
| **12/12/2026** | **14** | **5,0 %** | **262 j** | **falaise → coupe** |
| 31/12/2026 | 19 | 6,8 % | 243 j | falaise (postérieure) |
| 30/06 → 02/07/2027 | 43 → 52 | 15 → 19 % | 62 → 60 j | fin d'année scolaire, conservée |

Ce critère met les **exports glissants de Tisséo (35 jours) hors d'atteinte par
construction** : aucune de leurs dates n'a treize semaines de couverture derrière
elle. Vérifié : leur pic maximal de pertes vaut 2 lignes (1,6 %), celui du TER 0, et
les quatre feeds Tisséo/TER reconstruits sont identiques à l'octet près.

Seuils dans `feed_year.yaml` : `falaise_lignes_part_min` (0,04 du maximum de lignes
actives), `falaise_lignes_min` (plancher absolu 5 — liO ne perd jamais plus de 4
lignes en sept jours par renouvellement saisonnier), `falaise_fenetre_jours` (7),
`falaise_jours_apres_min` (91). Un `falaise_lignes_part_min` nul désactive le
contrôle.

**Le prix de la coupe est déclaré, pas caché.** Écarter les 263 dates postérieures au
11/12/2026 prive `lio_2026` des classes `vac_hiver`, `vac_printemps`, `ete_juillet` et
`vac_noel` de leur donneur réel, et `lio_2027` de toutes ses journées réelles : les
journées en confiance basse passent de 5 à **192** pour 2026 et de 0 à **179** pour
2027, et le build sort en code 4. Ces journées sont des vacances et du mois de
juillet ; la journée simulée est un lundi scolaire, et elle y gagne 809 courses. Une
approximation déclarée vaut mieux qu'une sous-offre silencieuse de 21 % sur la journée
mesurée. **Un export liO publié après le changement de service de décembre 2026
rendrait ces 263 dates réelles sans changer une ligne du pipeline.**

### 2. Une seule source autoritaire par date

Une date couverte par plusieurs exports ne prend son offre que dans **un** seul :
le plus récemment publié, celui qui intègre les dernières décisions
d'exploitation. Jamais d'union — c'est elle qui sur-servait.

### 3. Classer chaque journée par signature

`signature = (type de jour, classe de période)` où le type de jour est
`lun…dim` ou **`ferie`**, et la classe de période l'une de `scolaire`,
`vac_hiver`, `vac_printemps`, `pont_ascension`, `ete_juillet`, `ete_aout`,
`vac_toussaint`, `vac_noel`.

Le calendrier scolaire de la zone C explique l'offre de très près : les bornes
officielles coïncident avec les ruptures mesurées (chute de 12 600 à 10 535 trips
le lundi 20/04, retour à 12 538 le lundi 04/05, vendredi de pont 15/05 réduit à
10 877).

**Un férié n'est pas un dimanche.** Le 14/07 sert 5 674 trips contre 4 683 à
5 054 pour les dimanches de juillet ; le 08/05, 4 782 contre 4 644. L'écart est
d'environ 10 %, d'où une signature distincte.

**Les bornes de période sont apprises, pas postulées.** Le samedi 18/04, premier
jour officiel des vacances de printemps, roule encore en samedi scolaire
(8 194 trips, comme les samedis scolaires précédents, contre 8 470 le samedi de
vacances suivant) ; le premier samedi des vacances d'été, lui, bascule tout de
suite. Le pipeline essaie plusieurs décalages de début et retient celui qui
minimise la dispersion à l'intérieur de chaque signature. Sur 2026 il apprend
`vac_printemps +1 j` et `ete_aout +2 j`.

### 4. Choisir le donneur par proximité de saison

Une date sans couverture reçoit la journée réelle de même signature la plus
proche **au sens des saisons** — `min(Δ, 365 − Δ)` sur le jour de l'année, pas
l'écart calendaire. Sans cela, un 5 janvier chercherait son donneur à 259 jours
(le 21 septembre) alors que le 16 mars, à 70 jours de saison, lui ressemble
davantage ; et une année entièrement copiée sur la précédente n'aurait que des
donneurs « lointains ».

Quand une classe de période n'a aucune journée réelle, une chaîne de repli
déclarée dans `feed_year.yaml` prend le relais, et la journée est marquée en
**confiance basse**.

### 5. Reconstruire le calendrier par ensembles de dates

Les trips qui roulent exactement les mêmes jours partagent un `service_id`
synthétique (`SVC_0001`…, numérotés par cardinalité décroissante).

Cela rend la sur-offre structurellement impossible, garde `calendar.txt` vide et
`exception_type=1` — les deux conditions posées par
[`llm-agents/inputs/gtfs/reader.py`](../../llm-agents/inputs/gtfs/reader.py) —
et compresse le calendrier d'un facteur dix : 8 812 services et 428 046 lignes,
là où un service par trip en demanderait plus de 3,7 millions.

### 6. Identifier les trips par leur contenu

Puisque le `trip_id` n'est pas stable, l'identité retenue est le hachage de
`(ligne, sens, girouette, géométrie, suite d'arrêts horodatés)`. Deux exports qui
décrivent la même course la partagent ; un identifiant recyclé pour une course
différente est **forké** en `<trip_id>__<export>` plutôt qu'arbitré en silence.
Sur 2026 : 187 755 fusions par contenu et 2 161 forks.

`(trip, horaires, géométrie)` est indissociable, parce que le
`shape_dist_traveled` des horaires est calibré sur **sa** géométrie. Une
géométrie qui diverge est **dupliquée** en `<shape_id>__<export>`, jamais
fusionnée point par point. Exemple réel : la shape `15805` de la ligne 174 passe
de 719 à 790 points entre juillet et août 2026 (déviation de tracé, +130 m) — les
2 161 forks en découlent presque tous.

**Deux courses de contenu identique le même jour sont deux courses.** liO en
publie 45 le lundi 14/09/2026 — deux numéros de mission pour un même horaire sur
une même ligne. Les fusionner amputerait l'offre de la journée, et V2 le
refuserait. Chaque course prend donc la **première « place » dont les jours
n'empiètent pas sur les siens** : identiques le même jour, elles restent deux ;
identiques sur des jours disjoints, elles n'en font qu'une — c'est ce second cas
qui comprime le feed, et le distinguer ferait passer `tisseo_2026.zip` de 22,1 à
29,4 Mo pour la même offre.

### 7. Lire les deux formes de calendrier

Tisséo et le TER ne publient que des dates explicites (`calendar_dates.txt`).
**liO publie 457 services hebdomadaires** dans `calendar.txt`, que
`calendar_dates.txt` corrige ensuite dans les deux sens : 3 408 ajouts
(`exception_type=1`) et **2 925 retraits** (`exception_type=2`). Le calendrier
est déplié en dates explicites à l'indexation — ignorer les retraits ferait
rouler des cars les jours où l'opérateur dit qu'ils ne roulent pas. Le feed
produit, lui, reste toujours en dates explicites avec un `calendar.txt` vide
(invariant V1).

Arrêts, lignes et correspondances relèvent en revanche de l'**infrastructure** :
le dernier export publié fait foi, et un arrêt qui bouge de plus de 25 m lève une
`[ALARME]` plutôt que d'être arbitré en silence (47 cas sur 2026, le pire à
137 m). Un `stop_id` n'est jamais suffixé : dédoubler un quai créerait deux
arrêts distincts dans OTP et dégraderait les correspondances.

---

## Ce qui est vérifié

Le feed produit est revalidé en **relisant les fichiers écrits**, jamais en
faisant confiance aux structures en mémoire.

L'invariant central est l'**empreinte d'offre** :

```
empreinte(feed, date) = sha256(multiensemble trié des clés de contenu
                               des trips actifs ce jour-là)
```

La « préservation à l'octet près » n'aurait pas de sens — les `service_id` sont
réécrits par construction. Ce qui doit être préservé, c'est l'offre.

| Contrôle | Ce qu'il exige | Gravité |
|---|---|---|
| **V1** | `calendar.txt` vide, `exception_type ⊆ {1}` | bloquant |
| **V2** | Sur chaque journée réelle, empreinte **strictement égale** à celle de sa source | bloquant |
| **V5** | Horaires monotones dans leur course, heures > 24:00:00 tolérées | bloquant |
| **V6** | `shape_dist_traveled ≤` longueur de la géométrie + 1 m — **détecte les tracés chimères**. Bloquant si le build a fabriqué le dépassement ; **alarme** s'il est déjà dans la source (liO en publie 29 sur 7 715 courses) | bloquant / alarme |
| **V7** | Une journée copiée sert **exactement** l'offre de son donneur, empreinte contre empreinte | bloquant |
| **V7c** | Note : une journée copiée peut sortir de l'enveloppe de volume de sa signature dans l'année cible, quand son donneur vient d'une autre année | note |
| **V7b** | Hétérogénéité de la source elle-même — informatif, pas un défaut du build | note |
| **V8** | Aucune journée de l'année sans offre ; plancher de lignes calibré sur le réseau | alarme |
| **V9** | `(service_id, date)` et `(trip_id, stop_sequence)` uniques | bloquant |
| — | Fermeture référentielle dans les deux sens, stations parentes comprises | alarme |

Les quatre feeds passent tous les contrôles bloquants.

**V7b est une observation utile** : la période scolaire n'est pas homogène.
L'offre décroît sur les dernières semaines de juin (11 102 trips le lundi 29/06
contre 12 522 le 08/06, soit 14 % de dispersion intra-signature). Le choix du
donneur par proximité de saison rend cette hétérogénéité inoffensive, mais elle
est réelle et vaut d'être connue.

### Les tests unitaires

```
make test-gtfs-year        # 50 tests, feeds synthétiques, aucun accès réseau, <1 s
```

Chaque test porte sur une décision qui, prise à l'envers, produit un feed
plausible mais faux : la sur-offre par union, le `trip_id` recyclé confondu avec
la course d'origine, la géométrie entrelacée, le creux d'un férié pris pour une
troncature, le férié traité comme un dimanche, l'écart saisonnier non cyclique.

Deux faiblesses ont été trouvées en les écrivant, et corrigées :

- **La référence de la coupe pouvait être contaminée par la queue qu'elle devait
  détecter.** Un export livré tardivement, majoritairement composé de sa propre
  queue, voyait sa médiane tomber au niveau de celle-ci — plus rien n'était « sous
  le seuil » et l'export passait intact. La référence est désormais le maximum
  par type de jour, plus un plancher absolu à 15 % du maximum de l'export.
- **Deux courses de contenu identique le même jour étaient confondues en
  silence.** Le cas ne se produit sur aucun export 2026 (compteur à zéro sur les
  quatre feeds) et V2 l'aurait bloqué, mais il lève maintenant une `[ALARME]`
  nommée au lieu de reposer sur le filet.

### Le hold-out

Un modèle d'extrapolation non testé n'est que plausible. On masque donc un mois
réel, on laisse le pipeline le reconstruire, et on compare :

```
make gtfs-year-holdout HOLDOUT=202605
```

Sur mai 2026 — 30 journées masquées, couvrant un mois ouvré, deux jours fériés
(08/05, 25/05), le pont de l'Ascension et deux week-ends :

**écart maximal 5,3 %, médiane sous 1 %**, tolérance fixée à 15 %. Les plus gros
écarts portent sur les samedis et dimanches de vacances (3 à 5 %) ; les jours
ouvrés scolaires tombent sous 1,2 %.

---

## Limites déclarées

- **48 journées de vacances n'ont aucune donnée réelle en 2026** — vacances
  d'hiver, de la Toussaint et de Noël. Elles sont copiées depuis les vacances de
  printemps, seule classe « vacances scolaires » observée, et marquées en
  confiance basse. Biais connu : l'offre de Noël est réellement plus faible que
  celle de printemps. Un export d'automne ou d'hiver les remplacerait sans
  changer une ligne du pipeline.
- **Les fériés du 01/01, du 15/08 et du 25/12 n'ont aucun donneur de même
  nature** et restent en confiance basse quoi qu'on fasse.
- **97 journées de 2026 et 82 de 2027 sont en confiance basse** pour Tisséo ; le
  build sort alors en code 4, traduit en succès par la cible Make mais en le
  disant.
- **liO n'a qu'un export, et il est tronqué au changement de service de décembre
  2026.** Sa fenêtre fiable court du 01/08 au 11/12/2026 (133 journées), d'où
  **192 journées en confiance basse sur `lio_2026` et 179 sur `lio_2027`** : les
  classes `vac_hiver`, `vac_printemps`, `ete_juillet` et `vac_noel` n'ont aucun
  donneur réel et passent par la chaîne de repli. La journée simulée du 16 mars
  2026, elle, est un lundi scolaire copié du **lundi 07/12/2026** — signature
  exacte, 99 jours de saison d'écart, **4 303 courses**. Sa confiance est déclarée
  **basse** parce que l'écart de saison dépasse 60 jours, alors que l'écart d'offre
  mesuré entre les deux périodes sur les 41 lignes du périmètre décrites dans les
  deux vaut **1,2 %** : l'étiquette est conservatrice. **Un export liO publié après
  décembre 2026 rendrait 263 dates réelles** et ferait tomber ces deux compteurs.
- **Le 1er mai reste sans service.** Ce n'est pas un trou de couverture : les
  deux exports qui l'englobent l'omettent tous les deux. L'extrapoler
  inventerait de l'offre. La règle est reconduite d'année en année sur le jour et
  le mois, et déclarée dans `feed_year.yaml`.
- **Le changement d'heure du 25/10** fait exister deux fois une course de 02:30
  en heure locale. Le donneur retenu (un dimanche de printemps) n'a pas ce
  problème ; V5 tolère.
- **Les vacances d'été 2027 sont bornées au 31 août par hypothèse** : l'API ne
  publie que leur date de début tant que le calendrier de l'année scolaire
  suivante n'est pas paru.

---

## La fenêtre GAMA

OTP consomme le feed annuel sans difficulté. **GAMA non** : son calendrier de
services est un masque binaire 64 bits — `assert len(all_dates) <= 64` dans
[`llm-agents/inputs/gtfs/gama.py`](../../llm-agents/inputs/gtfs/gama.py), décodé
côté modèle par `PublicTransport.gaml` (`trip_calendar_map`, `BITWISE_BIT_VAL`).
`build_trips` balaie de surcroît tous les trips pour chaque date, ce qui rend un
feed annuel impraticable de toute façon.

D'où une fenêtre :

```
make gtfs-window START=2026-03-16 DAYS=64
```

Elle **doit** contenir la date de simulation (`starting_date` dans
`GAMA/CityTransport/models/Settings.gaml`) : hors calendrier,
`is_trip_available_today` se contente d'un avertissement et ne planifie plus
aucune course. La fenêtre 2026-03-16 +64 j sert 63 dates, 34 356 trips, et passe
les deux `assert` du lecteur ainsi que le masque binaire.

`make gtfs-window` extrait la fenêtre **d'un** feed, à côté du jeu en service :
c'est l'outil d'inspection. Ce que GAMA lit vraiment est produit par
`make gama-trip-info`, qui fenêtre les **trois** réseaux, les fusionne et écrit
`GAMA/CityTransport/includes/trip_info.json` avec les couches en regard. Trois
choses y sont propres à la fusion, et non à un feed seul :

- **la date simulée est lue dans `Settings.gaml`**, pas recopiée — deux sources
  pour une même date finissent par diverger, et la conséquence d'une divergence
  est un réseau vide sans message d'erreur ;
- **`build_calendar_binary_map` compte un bit par JOUR de l'intervalle**
  `min(date) … max(date)`, pas par date servie : c'est l'**étendue** du calendrier
  fusionné qui doit tenir dans 64, et elle est vérifiée après la fusion ;
- **les `service_id` sont préfixés par réseau.** `ter_2026` et `lio_2026`
  numérotent tous deux leurs services `SVC_0001`… : **224 identifiants
  collisionnent** (règle 5 — la renumérotation est locale à chaque feed). Fusionnés
  tels quels, les cars liO liraient le calendrier des trains.

La source Tisséo de `trip_info.json` reste l'**export en service**, pas le feed
annuel : ce dernier forke les géométries divergentes en `<shape_id>__<export>`
(règle 6), et **329 de ses 705 `shape_id` sont absents de `routes.shp`** — un
`shape_id` de course sans tracé dans la couche rend `route first_with (…)` nil
côté modèle. Publier le feed annuel Tisséo demandera donc de refaire les couches
et les courses **ensemble**, ce que `make gama-trip-info` fait déjà.

Voir [`docs/setup/data-pipeline.md`](../setup/data-pipeline.md) § « Préparer les
données GTFS pour GAMA ».

---

## Recevoir de nouveaux exports

1. Déposer les zips dans un des répertoires listés sous `reseaux.<réseau>.exports`
   de [`feed_year.yaml`](../../scripts/data/gtfs_year/feed_year.yaml). Les
   doublons stricts (même md5) sont détectés et ignorés.
2. `make gtfs-year-dry` — quelles journées deviennent réelles, lesquelles restent
   copiées et depuis quand. Rien n'est écrit.
3. `make gtfs-year-holdout HOLDOUT=<AAAAMM>` sur un mois nouvellement couvert :
   la mesure vaut sur des données que le modèle n'a jamais vues.
4. `make gtfs-year` — les journées auparavant extrapolées qui sont désormais
   couvertes basculent en réel d'elles-mêmes ; le manifeste le dit.

Le build est **reproductible** : sortie triée, identifiants synthétiques stables,
zip sans horodatage, et un instantané versionné du calendrier scolaire
(`calendrier_snapshot.json`) qui permet de rejouer hors ligne. Les deux sources
de calendrier sont
[data.education.gouv.fr](https://data.education.gouv.fr) (vacances par zone) et
[calendrier.api.gouv.fr](https://calendrier.api.gouv.fr) (jours fériés).

---

## Publication

Les feeds sont produits **à côté** du jeu en service : ni `data/gtfs/` ni
`graph.obj` ne sont touchés par `make gtfs-year`.

Publier reste une décision explicite, et **change les résultats de simulation**.

### Ce qui est en service depuis le 2026-09-04

| Répertoire de `data/gtfs/` | Contenu |
|---|---|
| `tisseo_gtfs` | l'**export en service** de Tisséo (la publication du feed annuel Tisséo reste une décision à part) |
| `ter_gtfs` | **`ter_2026`, le feed annuel** — l'export en place (2026-04-29 → 2026-10-26) ne faisait rouler aucun train le 16 mars 2026 |
| `lio_gtfs` | **`lio_2026`, le feed annuel** — l'export liO ne couvre rien avant le 1ᵉʳ août 2026 |

Le graphe qui en résulte : 11 507 arrêts, 3 146 patterns, 84,4 Mo, construit en 55 s
et 2,1 Go de pointe. Les seize autorités servies sont Tisséo, SNCF Voyageurs et les
quatorze agences liO. Ancien graphe conservé sous
`data/gtfs/archives/2026-09-04_pre_lio/`.

### La procédure

1. Poser le feed **à la racine** de `data/gtfs/`, dans un répertoire suffixé
   `_gtfs` ou un zip de premier niveau — OTP ne regarde que ce niveau. Un ancien
   export se **déplace** sous `data/gtfs/archives/<date>_…/`, il ne se supprime pas,
   et il ne reste pas au premier niveau : deux calendriers pour un même réseau se
   cumuleraient.
2. `build-config.json` doit être **dans** `data/gtfs/` (c'est le cas depuis le
   ticket 031, T5) : celui d'`otp-toulouse/toulouse/` est hors du répertoire de
   build, donc inerte. `router-config.json` n'y est **toujours pas** — les trois
   instances tournent sur la configuration de routage par défaut, ce qui est une
   limite connue et non un choix.
3. Reconstruire le graphe :
   `java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --build data/gtfs --save`.
   Une publication du feed annuel Tisséo porterait le graphe de 39 343 à ~75 000
   trips : prévoir `-Xmx8G` et vérifier le `mem_limit: 6g` des trois réplicas.
4. `docker compose up -d otp1 otp2 otp3`, et vérifier les trois *healthchecks*.
5. **Vérifier les modes demandés à OTP.** Un réseau dans le graphe dont le mode
   n'est pas demandé est **introuvable**, sans aucun signal : le TER est resté dans ce
   cas du 2026-09-03 au 2026-09-04. `llm-agents/trip_helper/otp.py` demande
   aujourd'hui `bus`, `metro`, `tram`, `cableway` et `rail`, et
   `gtfs_modality_name_map` nomme les `route_type` 0, 1, **2**, 3 et 6.
6. **Vérifier que les conteneurs voient le nouveau feed.** La porte de proximité
   d'OTP (`_has_reachable_stop`, 1 500 m) énumère les feeds du premier niveau de
   `data/gtfs` : montée sur le seul `tisseo_gtfs`, elle refusait l'appel à OTP pour
   397 des 2 580 points de la population scellée v4. Le montage
   `./data/gtfs:/data/gtfs` d'`api`, `worker` et `controller` couvre les trois
   réseaux ; un seul feed trouvé lève un avertissement au démarrage.
7. Invalider les caches indexés sur le graphe, sinon un cache chaud resservirait
   **en silence** des plans calculés sur l'ancien.
8. `dvc add data/gtfs` — `data/gtfs` est un output DVC.

---

## Voir aussi

- [`docs/arch/routing.md`](routing.md) — les deux moteurs de calcul d'itinéraires
- [`scripts/data/gtfs_year/`](../../scripts/data/gtfs_year/) — le pipeline
- `docs/traces/<date>_gtfs_annee/` — manifeste, provenance jour par jour,
  empreintes d'offre, rapport de hold-out
- `data/gtfs/archives/2026-08-26_pre_year_feed/` — le jeu en service avant ce
  chantier, et les sept exports bruts qui ont servi à construire les feeds
