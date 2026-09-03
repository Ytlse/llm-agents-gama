# Ticket 033 — Classification du profil de confort piéton et mise à jour des propositions pour llm_agent_gama

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ce qui suit est une **spécification**.

## Description

Post-traiter les itinéraires piétons générés via OSMnx (`network_type="walk"`) pour en extraire un
**profil de confort de marche** et structurer ces métriques spatiales dans le flux de données envoyé
aux agents LLM dans l'environnement GAMA. L'objectif est de fournir à l'agent une représentation
explicite de la **qualité et de la sécurité de la marche** pour influencer sa prise de décision
(ex : compromis temps/confort).

Contrairement à la voiture, l'arbitrage piéton ne repose ni sur la vitesse, ni sur le coût : un
piéton se déplace à ~4–5 km/h partout. Ce qui distingue deux itinéraires à pied, c'est le confort et
la sécurité de l'environnement traversé (voie dédiée vs bord de voie rapide). Ce ticket suit la même
logique que le ticket 032 : un profil de trajet agrégé par distance, homogène et comparable entre
modes.

**Ce que le 033 partage avec le 032.** Même plomberie et mêmes choix d'architecture : profil calculé
**dans `_route_sync`**, agrégé **pondéré par la distance**, **transitoire** (il ne vit que jusqu'au
rendu de l'option LLM, aucune remontée GAMA), **nom de bloc propre au mode** (`bike_safety` à vélo,
`comfort_metrics` à pied — pas de conteneur générique, cf. YAGNI du 032), rendu en **texte
qualitatif** dans le gabarit, `None` si aucune arête, et même exigence de mesure calibration
avant/après sur jeux gelés.

**Divergence assumée avec le 032 (une seule).** Le 032 refuse tout score synthétique et ne livre que
des faits OSM bruts (parts de distance + `exposed_m` en maillon faible, **sans seuil**). Le 033 fait
un **choix différent, délibéré** : il expose en plus un **score de confort ordinal 1–4**
(`worst_comfort`), **seuillé à 10 % de la distance**. Ce n'est pas une dérive : c'est un parti-pris
pour offrir à l'agent piéton un repère ordinal simple, là où le vélo se juge à sa pire exposition en
mètres. Le score reste **adossé aux mêmes faits de distance** et n'invente aucune donnée absente
(pas de piège *vacuité ≠ perfection*).

---

## Tâches techniques

### T1 — Extraction du graphe piéton (`network_type="walk"`)

Aucune extraction nouvelle : le graphe `walk` est **déjà chargé et réchauffé au démarrage**
(`trip_helper/osmnx_direct.py`, `_GraphStore`, mode `foot` → `walk`). La tâche se limite à réutiliser
ce graphe en mémoire.

### T2 — Score de confort piéton (1 à 4), attribut statique d'arête

Poser un attribut `comfort` (1 à 4) sur chaque arête du graphe `walk`, **dans la boucle qui pose déjà
`data["speed_kph"]`** à la construction du graphe (`_GraphStore`). Le confort est donc un **attribut
statique**, calculé une seule fois et stocké dans le pickle du graphe — pas de recalcul par requête.

La classification repose sur le **seul tag `highway`** (toujours présent et fiable), avec `maxspeed`
en secondaire. On n'utilise **pas** `sidewalk`/`foot` : ces tags sont absents du graphe caché
(OSMnx par défaut ne les retient pas) et, à Toulouse, un trottoir est le plus souvent cartographié
comme `footway` séparé — déjà classé Confort 1.

| Classe | `highway` couverts |
|---|---|
| **1 — Voie dédiée / apaisée** | `footway`, `pedestrian`, `path`, `living_street`, `steps`, `track` |
| **2 — Rue résidentielle** | `residential`, `unclassified`, `service` |
| **3 — Axe urbain, trafic soutenu** | `tertiary`, `secondary`, `primary` |
| **4 — Bord de voie rapide** | `trunk` (et `primary` si `maxspeed` ≥ 70 km/h) |

Fallback : tout `highway` non listé retombe sur Confort 2 (rue ordinaire), sur le même principe que
le fallback vitesse existant. Aucune arête ne reste non classée.

### T3 — Agrégation et propagation dans le pipeline (pas de middleware JSON)

Le piéton est déjà routé par OSMnx (`osmnx_direct.py`, mode `foot`) : le profil s'agrège sur **les
arêtes exactes que le routeur retourne** — pas de problème d'alignement routage↔profilage. Le calcul
se fait **dans `_route_sync`** (là où la liste d'arêtes existe, aujourd'hui écrasée en
`{duration_s, distance_m}`) et se réduit à **trois sommes** :

- `comfort_1_pct` … `comfort_4_pct` : distribution en pourcentage de distance (somme = 100 %).
- `worst_comfort` : **pire niveau de confort couvrant au moins 10 % de la distance** du trajet. Un
  simple `max` serait dominé par un micro-segment ; le seuil de distance neutralise ce bruit. (NB :
  divergence assumée avec le 032, qui applique au contraire un maillon faible sans seuil — cf. la
  note de divergence en tête de ticket.)

**Ce n'est pas un formatage a posteriori dans un middleware.** GAMA ne reçoit **aucune proposition
d'itinéraire en réponse JSON** : le controller route en interne et pousse le plan. Le profil doit
donc traverser la chaîne **du routage jusqu'au rendu de l'option**, sur le modèle du ticket 032 :

1. `_route_sync` renvoie `{duration_s, distance_m, comfort_metrics}`.
2. **Cache** : le dict retour est stocké tel quel — `osmnx_persistent_cache.py` sérialise **tout le
   dict** dans `result_json`, et le réplica HTTP (`osmnx_server.py` `/route`) le renvoie tel quel.
   **Pas de numéro de version de schéma** : la clé est déjà préfixée par `routing_version()`, et la
   RAZ du 032 vide le fichier une fois — il ne reste aucune entrée ancienne à traiter en *miss*. Ne
   **pas** bumper `routing_version()` pour autant : le confort ne change pas la sémantique de
   `duration_s`, et un bump forcerait un recalcul à froid de milliers de routes (~2 h pour
   930 personas) pour un champ purement additif.
   Le chemin de *cache hit* est **déjà corrigé par le 032** (cf. son T3.2) : `_make_travel_plan` a
   gagné un paramètre optionnel **`route_extras`** portant le dict retour complet de `_route_sync`.
   ⇒ **le 033 n'ajoute aucune plomberie** : `comfort_metrics` voyage dans ce même dict, sans nouveau
   paramètre ni nouveau contrat. C'est tout l'intérêt d'avoir livré le 032 d'abord.
3. **Modèle** : `_make_travel_plan` porte `comfort_metrics` (`models.py`, champ `Optional[dict]`
   **transitoire**) sur le `TravelPlan`, le temps du rendu, extrait de `route_extras` selon le mode. **Pas de contrat GAMA** : le profil est une
   fonction déterministe de (graphe, OD, mode), donc recalculable hors ligne depuis le journal de
   mouvements — le propager dans `PersonMove` ferait voyager à chaque mouvement une donnée dérivable,
   pour zéro information nouvelle. S'il transite incidemment dans `model_dump`, aucun code aval ne
   s'en sert.

### T4 — Injection dans la décision LLM (texte rendu, pas JSON)

C'est l'objet réel du ticket. L'agent **ne lit pas de JSON** : il lit le **texte rendu** de chaque
option de déplacement.

- Ajouter le profil au dict d'option (`llm_agent.py`, `build_travel_plan_payload`) via une propriété
  de `TravelPlanWrapper` (`text_helper/models/travel_plan.py`).
- Le **rendre en texte qualitatif** dans le gabarit `travel_plan_describe_v2.j2` — p. ex. « Marche
  surtout en voie apaisée ; ~200 m le long d'un axe passant » — et non en pourcentages au point près.
- Mettre à jour le prompt système `itinary_multi_agent` (variante active `expert_chaine`,
  `llm_module/prompts/prompts.yaml`) pour qu'il pondère le confort dans l'arbitrage temps/confort.

> Le bloc porte un **nom propre au mode** (`comfort_metrics` à pied, `bike_safety` à vélo), comme le
> 032 : pas de conteneur multi-modes générique. L'agent, lui, ne voit **aucune de ces clés** — il lit
> le texte rendu ; les noms de bloc ne concernent que le code Python.

> Impact calibration (à cadrer, pas à ignorer). Éditer le texte des options / le prompt **purge
> automatiquement** le cache de décisions LLM (isolation par `active_prompt_checksum()`), mais
> déplace les parts modales : **mesurer sur jeux gelés avant/après**, n'ouvrir aucun run de
> production entre les deux (cf. *pas de dégradation scientifique*).

### T5 — Migration : reconstruction du graphe

L'ajout de l'attribut `comfort` change le pickle du graphe `walk`. Comme le 033 **n'ajoute aucun tag
OSM** (il n'utilise que `highway`, déjà retenu), la migration est **plus légère que celle du 032** :
pas de reconfiguration `useful_tags_way`. Elle suit néanmoins **la même séquence ordonnée en trois
temps** que le 032 (graphe → purge → repopulation), pour la même raison et avec le même piège :

1. **Reconstruire le graphe `walk` une seule fois** : le pickle `graphs_*.pkl` vit sur le **volume
   partagé** `./data/cache/osmnx` (monté par le controller et les réplicas) — on le régénère **une
   fois**, avec l'attribut `comfort` posé sur les arêtes, **pas par réplica**. Aucun bump de version
   de cache (cf. T3.2).
2. **Purger** le cache de routes OSMnx — **obligatoire**, et pas pour la justesse des durées (poser
   `comfort` ne change ni topologie ni `travel_time` : les itinéraires piétons sont identiques). La
   raison est que le peupleur est **idempotent par couverture** (`if not _sqlite.lookup(key).found`) :
   sans purge, il **saute** toutes les entrées existantes, qui survivent sans profil indéfiniment →
   cache durablement mixte, une part des options à pied avec ligne confort et une part sans, **sans
   aucune erreur**.
3. **Repeupler** avec le peupleur en masse (`scripts/data/population/route_worker.py`, étape 6 du
   notebook).

> ⚠ **L'ordre est contraignant** (comme au 032) : `init_worker` charge le pickle du graphe. Repeupler
> avant d'avoir reconstruit le graphe `walk` produit un cache intégralement peuplé et **uniformément
> sans profil de confort** — silencieux.

**Si les deux tickets sont livrés dans la même fenêtre**, la séquence est mutualisée : on reconstruit
les graphes `bike` **et** `walk`, on purge une fois, on repeuple une fois. Ne pas enchaîner deux
purges/repopulations successives.
- **Assertion au démarrage** (par process) : vérifier qu'une fraction non nulle des arêtes `walk`
  porte `comfort`, et échouer bruyamment sinon (piège *vacuité* : un profil systématiquement vide
  mentirait).
- Se **greffer sur la RAZ déjà prévue par le 032** (LTM + décisions LLM) plutôt que d'en déclencher
  une seconde, si les deux tickets sont livrés dans la même fenêtre.

---

## Critères d'acceptation (DoD)

1. 100 % de la distance du trajet est classifiée dans un niveau de confort (1 à 4), sans erreur sur
   les segments dont le `highway` n'est pas explicitement listé (fallback Confort 2).
2. **Absence d'arêtes ⇒ `comfort_metrics = None`** (pas de profil fabriqué) : cas du court-circuit
   `orig == dest` de `_route_sync`. Le gabarit **omet** alors la ligne confort.
3. Le profil **apparaît en texte** dans l'option lue par l'agent LLM ; aucune étape après la décision
   (remontée GAMA, exécution du mouvement, logs) n'en dépend (profil transitoire).
4. Un itinéraire **servi du cache** porte la **même ligne confort** qu'un itinéraire fraîchement
   calculé (chemin de *cache hit* corrigé, cf. T3.2) — cohérence du prompt.
5. Tests unitaires sur `gdf` synthétique : arête Confort 1/2/3/4, arête au `highway` non listé
   (fallback Confort 2), et le cas « aucune arête » ⇒ `None`.
6. **Migration** : la séquence des trois temps est respectée **dans l'ordre** (graphe `walk`
   reconstruit une fois sur le volume partagé → purge → repopulation) ; l'assertion « le graphe
   `walk` porte `comfort` » passe au démarrage de chaque process ; après repopulation, un
   **échantillon d'entrées du cache piéton porte `comfort_metrics`** — un cache repeuplé dont aucune
   entrée n'a de profil signale l'inversion d'ordre et doit échouer bruyamment.

**Ce que l'agent LLM lit réellement** (texte, extrait d'option) :

```
- [1] foot : Temps de trajet : ~18 min. Distance : ~1,4 km.
  Marche surtout en voie apaisée ; ~200 m le long d'un axe passant.
```

**Structure interne `comfort_metrics`** (transitoire, portée par le plan le temps du rendu ; `null`
si aucune arête). Invariant : `comfort_1_pct + … + comfort_4_pct` = 100 :

```json
{
  "worst_comfort": 3,
  "comfort_1_pct": 60,
  "comfort_2_pct": 25,
  "comfort_3_pct": 15,
  "comfort_4_pct": 0
}
```

---

## Dépendances

- **Ticket 032** : il pose la **plomberie réutilisable** — profil calculé dans `_route_sync`, porté
  **transitoirement** sur le `TravelPlan`, traversant le cache dans le dict retour (**chemin de
  *cache hit* corrigé**), rendu en texte qualitatif dans `travel_plan_describe_v2.j2`, prompt système
  mis à jour, reconstruction du graphe une fois sur le volume partagé + assertion au démarrage,
  RAZ LTM/caches. Il doit être stabilisé avant, pour que le 033 n'ait qu'à ajouter sa table de
  confort et ses sommes.

## Leviers / évolutions (hors scope livrable)

- **Escaliers (`stairs_count`)** : nombre de segments `highway=steps` sur le trajet (enjeu
  accessibilité / PMR). Trivial à ajouter (une somme de plus dans T3) mais retiré du scope v1 pour le
  garder minimal.
- **Traversées (`crossings_count`)** : nombre de nœuds `highway=crossing` sur le trajet. Signal de
  confort utile, lisible directement dans le graphe `walk` (les tags de nœuds sont retenus). Écarté de
  la v1 ; la variante « traversées d'axes majeurs » exigerait une superposition au réseau `drive`
  (coûteuse, fragile) et n'est pas retenue.
- **Éclairage nocturne (`lit`)** : séduisant vu la dimension temporelle de la simulation (jour/nuit),
  mais **écarté faute de donnée fiable** — mesure Overpass sur Toulouse : seules ~28 % des voies
  piétonnables portent le tag `lit` (8 747 / 31 559). Les 72 % restants sont *inconnus*, pas
  *non éclairés* ; un `unlit_pct` serait donc trompeur. À reconsidérer si la couverture progresse.

## Ce que ce ticket ne fait pas

- Il ne modifie pas le routage OSMnx sous-jacent (sélection du chemin optimal) : le profil est
  calculé **dans le worker de routage** (`_route_sync`), sur les arêtes du chemin déjà choisi — ce
  n'est pas un post-traitement en aval (la `gdf` n'existe plus une fois `_route_sync` terminé).
- Il ne tient pas compte du **dénivelé** : celui-ci exigerait un Modèle Numérique de Terrain (MNT)
  externe, dépendance absente des modes vélo/voiture ; il pourra faire l'objet d'un ticket dédié.
- Il ne profile pas les **tronçons de marche internes à un itinéraire multimodal OTP** (rabattement
  vers les TC) : ceux-ci ne passent pas par le graphe OSMnx `walk` et n'ont pas de liste d'arêtes à
  profiler ; seul le trajet piéton direct (`foot`) est couvert.
- Il ne crée pas d'interface utilisateur pour visualiser le profil de confort dans GAMA ou Grafana,
  ni de lecture GAMA-side du champ.
- Le profil **ne survit pas** à la sélection : pas de propagation GAMA, pas de persistance ni d'usage
  après la décision (transitoire, comme au 032). Un analyste qui en aurait besoin le **recalcule**
  depuis le journal de mouvements (origine/destination/mode), le profil étant déterministe.
- Il ne (re)calibre **pas** le prompt : il en **signale** l'impact et exige la mesure avant/après.
