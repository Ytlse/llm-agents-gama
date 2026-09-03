# Ticket 032 — Profil de sécurité du trajet vélo (données OSM) et mise à jour des propositions pour llm_agent_gama

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ce qui suit est une **spécification**.

## Description

Exposer à l'agent LLM, pour chaque itinéraire cycliste calculé via OSMnx, un **profil de sécurité
descriptif** dérivé des tags OSM des arêtes du chemin (aménagement cyclable, hiérarchie de voirie,
vitesse), afin d'éclairer son arbitrage temps/sécurité. Le profil est **factuel** : il décrit ce
que le trajet traverse, sans prétendre reconstituer le *Level of Traffic Stress* (LTS) normé.

**Choix de rigueur (assumé).** Le LTS normé (Furth/Mineta) exige le nombre de voies, le
stationnement latéral et le trafic (ADT), **indisponibles** dans un graphe OSMnx
`network_type="bike"`. Revendiquer un « score LTS 1-4 » à partir des seuls `cycleway`/`highway`/
`maxspeed` serait une fausse précision, et un repli silencieux (tout classer « sûr » quand la
donnée manque) produirait un score parfait qui n'est en réalité qu'une absence de mesure. Le
ticket livre donc des **faits OSM agrégés**, chacun défendable à la source, et signale
explicitement ce qui n'est pas mesuré. Un indicateur de stress synthétique reste possible plus
tard, **au-dessus** de ces faits et clairement étiqueté « heuristique OSM », hors de ce ticket.

Le champ produit est **spécifique au vélo** (`bike_safety`) et volontairement simple. On ne
construit pas de conteneur multi-modes générique tant que le ticket 033 (voiture) est réécrit et sa
forme inconnue : une abstraction prématurée risquerait d'être la mauvaise. La généralisation se
fera quand la structure du 033 sera connue (YAGNI).

---

## Tâches techniques

### T1 — Attributs de sécurité par arête

Sur la `gdf` par arête du chemin cycliste — déjà matérialisée dans `_route_sync`
(`trip_helper/osmnx_direct.py`, `route_to_gdf`) mais aujourd'hui écrasée en `{duration_s,
distance_m}` — extraire pour chaque arête : aménagement cyclable (`cycleway`), type de voie
(`highway`), vitesse légale (`maxspeed`), longueur (`length`).

- **`maxspeed`** est **déjà retenu** par OSMnx (tags par défaut) : il est présent dans la `gdf`.
  Le parsing **réutilise l'outillage osmnx** (gère `mph`, listes) plutôt qu'un parseur maison ; ce
  qu'osmnx ne convertit pas (`"FR:urban"`, vide, absurde) tombe sur le **fallback `highway`**
  (table dédiée « limite légale » en YAML, ex. `residential` → 30, `primary` → 50). Table
  **exhaustive** (voiries cyclables connues), **sans catch-all** : un `highway` inconnu sans
  `maxspeed` reste non classé → alarme couverture (DoD #2), plutôt qu'une vitesse devinée en silence.
- **`cycleway`** n'est **pas** retenu par défaut : étendre les tags téléchargés **pour le graphe
  vélo uniquement** (pas walk/drive, afin de limiter la taille du pickle et la RSS des workers),
  puis **reconstruire** le cache `graphs_*.pkl`.
- La table de classification (aménagement / voirie / seuils de vitesse → catégorie) vit en
  **config YAML** (`config/osmnx.yaml`, sur le modèle des blocs `speeds`/`fallbacks` existants),
  jamais codée en dur.

> Note de cohérence : la vitesse de sécurité (`maxspeed`, limite légale) est un concept
> **distinct** de la vitesse de parcours vélo (`speed_kph` dérivée du `highway` pour le temps de
> trajet). Ne pas les fusionner : ce sont deux mesures légitimement différentes de la même arête.

**Seuils de vitesse (validés).** Ancrés sur la réglementation française — **30 km/h** (zone 30 /
zone de rencontre), **50 km/h** (défaut urbain), **> 50 km/h** (voie rapide) — et cohérents avec la
littérature OSM→LTS de référence, qui place une voie partagée **> 50 km/h sans aménagement au
niveau le plus stressant** (BikeOttawa, Conveyal). Ils sont figés en YAML.

**Définition de « protégé » (validée).** Seule une **séparation physique** compte : `highway=cycleway`,
`highway=path` (`bicycle=designated`), ou `cycleway=track`/`separated`. Une **bande peinte**
(`cycleway=lane`) et une granularité **inconnue** (`cycleway=yes`) ne sont **pas** « protégé » :
elles sont classées par la vitesse de la voie (donc `exposé` si > 50). « Inconnu ≠ protégé ».

### T2 — Agrégation en profil descriptif

Calculer sur l'ensemble des arêtes, **pondéré par la distance** :

- `protected_pct` : part de distance sur aménagement cyclable dédié (`cycleway`) ;
- `calm_pct` : part sur voie partagée ≤ 30 km/h (zone 30 / rencontre) ;
- `urban_pct` : part sur voie partagée 30–50 km/h (défaut urbain) ;
- `exposed_m` : longueur cumulée sur voie > 50 km/h **sans aménagement** (mètres) — le vrai
  facteur de stress ;
- `max_speed_kmh` : vitesse légale maximale rencontrée ;
- `classified_pct` : part de distance effectivement classée (100 % attendu grâce au fallback ;
  un écart déclenche l'alarme, cf. DoD).

On ne calcule **pas** de `worst_lts` : le « max pondéré par la distance » de la version initiale
était incohérent (un max n'est pas une pondération). L'exposition est exprimée en **longueur**.

> Principe du « maillon faible » (BikeOttawa, Conveyal) : un trajet se juge au niveau de son pire
> segment — une fin de bande cyclable qui jette dans une voie rapide déclasse tout le trajet. Donc
> `exposed_m` **ne seuille pas** les courts segments : même 20 m exposés sont comptés et signalés
> dans le texte de l'option. Inconnu ≠ sûr ; court ≠ négligeable.

### T3 — Propagation transitoire jusqu'au rendu de l'option

Le calcul se fait **dans `_route_sync`** (là où vit la `gdf`). Le profil est **transitoire** : il
ne doit voyager que du routage jusqu'au **rendu de l'option LLM**, pas au-delà.

1. `_route_sync` renvoie `{duration_s, distance_m, bike_safety}`.
2. **Cache** : le dict retour est stocké tel quel — le cache SQLite (`osmnx_persistent_cache.py`)
   sérialise **tout le dict** dans `result_json`, et le réplica HTTP (`osmnx_server.py` `/route`,
   `_get_direct_plan_http`) le renvoie tel quel. ⇒ côté **écriture**, `bike_safety` transite sans
   aucun changement de schéma. On le garde en cache pour que les itinéraires servis du cache aient
   la même ligne sécurité que les fraîchement calculés (cohérence du prompt).

   ⚠ **Mais le chemin de *cache hit* doit être modifié** — il ne suffit pas de stocker. Le *hit*
   déballe aujourd'hui **deux clés nommées** (`entry.result["duration_s"]`,
   `entry.result["distance_m"]`) pour appeler `_make_travel_plan` : le profil serait écrit en cache
   puis **jeté silencieusement à la relecture**. Sans cette correction, les itinéraires du cache
   seraient rendus **sans** ligne sécurité et les fraîchement calculés **avec**, sans aucune erreur
   pour le signaler — exactement l'incohérence de prompt que ce point vise à éviter. C'est le
   **seul** endroit de la chaîne qui re-nomme les clés : source, `/route` du réplica, client HTTP,
   `store`/`lookup` et le **peupleur en masse** (`scripts/data/population/route_worker.py` +
   notebook étape 6) manipulent tous le dict entier et sont déjà transparents.

   **Forme du correctif (validée) : un paramètre additif `route_extras`.** `_make_travel_plan` a
   **6 appelants** — 2 en production et **4 dans `tests/test_terminal_time.py`**. Sa signature ne
   passe donc **pas** en « prends un dict » (cela casserait les 4 tests pour rien) : elle gagne un
   paramètre **optionnel** `route_extras: Optional[dict] = None` portant le **dict retour complet**
   de `_route_sync`, dont `_make_travel_plan` extrait le bloc du mode. Les appels de test restent
   intacts (défaut `None`), et le **ticket 033 n'ajoute aucune plomberie** : son `comfort_metrics`
   voyage dans le même dict, sans nouveau paramètre.

   **Pas de numéro de version de schéma.** La clé est déjà préfixée par `routing_version()` et la
   RAZ (T5) purge le fichier une fois : il ne reste aucune entrée ancienne à traiter en *miss*. Ne
   **pas** bumper `routing_version()` non plus — `bike_safety` ne change pas la sémantique de
   `duration_s`, et un bump forcerait un recalcul à froid de milliers de routes (~2 h pour
   930 personas) pour un champ purement additif.
3. **Modèle** : `_make_travel_plan` porte `bike_safety` (`models.py`, champ `Optional[dict]`
   **transitoire**) sur le `TravelPlan`, le temps du rendu. **Pas de contrat GAMA** : le profil
   n'est ni requis ni consommé après la décision (s'il transite incidemment dans `model_dump`,
   aucun code aval ne s'en sert — cf. Non-goals).

### T4 — Injection dans la décision LLM (texte, pas JSON)

C'est l'objet réel du ticket. L'agent **ne lit pas de JSON** : il lit le **texte rendu** de chaque
option (durées en tranches, distances humanisées).

- Ajouter le profil au dict d'option construit dans `llm_agent.py`
  (`build_travel_plan_payload`, entrée `trajectories[]`), via une propriété de
  `TravelPlanWrapper` (`text_helper/models/travel_plan.py`).
- Le **rendre en texte qualitatif** dans le gabarit `travel_plan_describe_v2.j2`, cohérent avec la
  granularité existante — p. ex. « Trajet surtout en site cyclable protégé ; ~300 m exposés au
  trafic rapide » — et **non** en pourcentages au point près.
- Mettre à jour le prompt système `itinary_multi_agent` (variante active `expert_chaine`,
  `llm_module/prompts/prompts.yaml`) pour qu'il pondère ce profil dans l'arbitrage.

> Impact calibration (à cadrer, pas à ignorer). Éditer le texte des options / le prompt **purge
> automatiquement** le cache de décisions LLM (isolation par `active_prompt_checksum()`). Mais
> déplacer le texte déplace les parts modales, donc la loss de calibration bouge : **mesurer sur
> jeux gelés avant/après** et n'ouvrir aucun run « de production » entre les deux.

### T5 — Migration : reconstruction du graphe et RAZ des caches / mémoires

L'ajout du tag `cycleway` et du profil change des artefacts persistants. La migration est une
**séquence ordonnée en trois temps** — l'ordre n'est pas un détail, cf. l'avertissement ci-dessous :

1. **Reconstruire le graphe vélo, une seule fois.** Le pickle `graphs_*.pkl` vit sur le **volume
   partagé** `./data/cache/osmnx` (monté par le controller et les réplicas) : on le régénère depuis
   OSM avec `cycleway` retenu, **une fois**, pas par réplica.
2. **Purger le cache de routes OSMnx** (SQLite persistant + cache de plans), la mémoire long terme
   (LTM) et le cache de décisions LLM.
3. **Repeupler** le cache de routes avec le peupleur en masse
   (`scripts/data/population/route_worker.py`, étape 6 du notebook `generate_population.ipynb`).

> ⚠ **L'ordre est contraignant.** `init_worker` charge le **pickle du graphe** depuis le cache
> partagé. Repeupler avant d'avoir reconstruit le graphe produit un cache intégralement peuplé et
> **uniformément sans profil** — le pire cas, et parfaitement silencieux (aucune erreur, juste une
> ligne sécurité qui n'apparaît jamais). Graphe **d'abord**, purge ensuite, peuplement en dernier.

**Pourquoi la purge est obligatoire** (et ce n'est pas pour la justesse des durées) : le peupleur est
**idempotent par couverture** — l'étape 6 teste `if not _sqlite.lookup(key).found` avant de calculer.
Sans purge, la repopulation **saute toutes les entrées existantes** et les entrées sans profil
survivent indéfiniment : aucune ne sera jamais recalculée. Le cache resterait durablement **mixte**,
une part des options vélo avec ligne sécurité et une part sans, **sans aucune erreur** — biais
silencieux introduit dans la mesure de calibration avant/après elle-même.

À l'inverse, la purge **n'est pas** justifiée par un changement de routage : retenir `cycleway` en
plus ne change ni la topologie ni `travel_time`, donc **routes et durées sont identiques**. Seule
l'homogénéité du profil l'impose. Corollaire : ne **pas** bumper `routing_version()` (cf. T3.2).

- **Assertion au démarrage** (par process) : vérifier que les arêtes du graphe vélo portent
  effectivement `cycleway` (au moins une fraction non nulle). À défaut, échouer bruyamment — sinon
  la classe « protégé » est silencieusement impossible et le profil ment (piège *vacuité*).
- La RAZ de la LTM et des décisions LLM est un choix assumé : on repart d'un état vierge plutôt que
  de gérer la coexistence d'anciens souvenirs sans profil. Cela règle aussi la question de la clé de
  récupération LTM (plus d'historique à faire correspondre).

---

## Critères d'acceptation (DoD)

1. Le calcul ne lève **aucune erreur** sur les arêtes sans `maxspeed` (fallback par `highway`) ni
   sur un `maxspeed` mal formé (liste, unité, `"FR:urban"`).
2. Sur un chemin réel, **`classified_pct == 100`** ; un écart est **compté** et **alarmé une fois**
   en `ERROR [ALARME]` (sur le modèle de `terminal_time_out_of_perimeter`), jamais masqué.
3. **Absence d'arêtes ⇒ `bike_safety = None`** (pas de profil fabriqué). Cas visé : le
   court-circuit `orig == dest` de `_route_sync` (points sur le même nœud / hors graphe). Le
   gabarit **omet** alors la ligne sécurité, comme il omet déjà d'autres inconnues.
4. Le profil **apparaît en texte** dans l'option lue par l'agent LLM ; aucune étape après la
   décision (remontée GAMA, exécution, logs) n'en dépend (profil transitoire).
5. Un itinéraire **servi du cache** porte la **même ligne sécurité** qu'un itinéraire fraîchement
   calculé (chemin de *cache hit* corrigé, cf. T3.2) — testé explicitement : stocker puis relire une
   entrée doit restituer `bike_safety`, pas le perdre.
6. **Tests unitaires** sur `gdf` synthétique : arête protégée, arête ≤30, arête 30–50, arête >50
   sans aménagement, arête sans `maxspeed`, `maxspeed` en liste/mph, et le cas « aucune arête »
   ⇒ `None`.
7. **Migration** : la séquence des trois temps est respectée **dans l'ordre** (graphe reconstruit
   une fois sur le volume partagé → purge → repopulation) ; l'assertion « le graphe vélo porte
   `cycleway` » passe au démarrage de chaque process ; après repopulation, un **échantillon
   d'entrées du cache vélo porte `bike_safety`** — un cache repeuplé dont aucune entrée n'a de
   profil signale l'inversion d'ordre (graphe non reconstruit) et doit échouer bruyamment.

**Ce que l'agent LLM lit réellement** (texte, extrait d'option) :

```
- [1] bicycle : Temps de trajet : ~15 min. Distance : ~3,0 km.
  Trajet surtout en site cyclable protégé ; ~300 m exposés au trafic rapide.
```

**Structure interne `bike_safety`** (transitoire, portée par le plan le temps du rendu ; `null` si
aucune arête). Invariant : `protected_pct + calm_pct + urban_pct + exposed_pct` = `classified_pct` ;
`exposed_m` est fourni en plus (longueur absolue, maillon faible) :

```json
{
  "protected_pct": 80,
  "calm_pct": 10,
  "urban_pct": 0,
  "exposed_pct": 10,
  "exposed_m": 300,
  "max_speed_kmh": 70,
  "classified_pct": 100
}
```

---

## Ce que ce ticket ne fait pas

- Il ne calcule **pas** le LTS normé (Furth/Mineta) : le graphe vélo ne porte ni voies, ni
  stationnement, ni ADT. Il livre des **faits OSM descriptifs**, extensibles.
- Il ne modifie **pas** le routage OSMnx (sélection du chemin) : le profil est extrait **dans le
  worker de routage**, sur les arêtes du chemin déjà choisi — mais il n'est **pas** un
  post-traitement en aval (la `gdf` n'existe plus une fois `_route_sync` terminé).
- Il ne (re)calibre **pas** le prompt : il en **signale** l'impact et exige la mesure avant/après.
- Il ne crée **pas** d'interface de visualisation (GAMA, Grafana) ni de lecture GAMA-side du champ.
- Le profil **ne survit pas** à la sélection : pas de propagation GAMA, pas de persistance ni
  d'usage après la décision. Il n'existe que pour le rendu de l'option (transitoire).

---

## Références

Les seuils de vitesse et la logique de classification s'appuient sur la littérature OSM→LTS ci-dessous
(sources externes, revues et **validées** le 2026-09-03 ; figées dans `config/osmnx.yaml`). La
spécification testable dérivée de ce ticket vit dans `specs/profil_securite_velo.md`.

- **BikeOttawa/stressmodel** — modèle OSM→LTS de référence, règles par tag ; ruptures ~40/50/64
  km/h ; principe « trajet = pire segment » ; `cycleway=track`≡`lane`. <https://github.com/BikeOttawa/stressmodel>
- **Conveyal — Cycling Level of Traffic Stress** — synthèse méthodologique. <https://docs.conveyal.com/learn-more/traffic-stress>
- **LTS-OSM (mbonsma)** — adaptation avec intersections. <https://github.com/mbonsma/LTS-OSM>
- **« Evaluating OpenStreetMap's Performance Potential for LTS Analysis »** (Empirical Urbanist) —
  taux d'erreur, forte sensibilité au `maxspeed` manquant (justifie fallback + alarme couverture).
  <https://empirical-urbanist.io/publications/osm-and-lts>
- **CEREMA EMC²** — hiérarchie des modes / dimensionnement, ancre réglementaire française
  (zone 30 / 50 / voie rapide) pour caler les seuils au contexte toulousain.
