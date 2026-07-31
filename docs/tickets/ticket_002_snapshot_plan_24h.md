# Ticket 002 — Sauvegarde/rechargement du plan 24h (snapshot de warm-up)

## Description

Au `/init`, le warm-up `bootstrap_all_agents` (`urban_mobility_agents/simulation_controller.py:762`)
calcule pour chaque agent son premier trajet, puis remplit une file glissante 24h
`state.precomputed_moves: deque[PersonMove]` (`models.py:222`). Ce calcul mobilise
**deux ressources coûteuses** : le routage (OTP/osmnx) **et** les décisions LLM.

GAMA reste bloqué sur la réponse HTTP de `/init` pendant toute cette phase. Sur une
population de taille réaliste, le warm-up domine le temps de démarrage et il est
**recalculé intégralement à chaque run**, même quand rien n'a changé.

L'objectif est de **sauvegarder le plan 24h résolu** (décisions LLM incluses) et de
le **recharger au run suivant** pour court-circuiter entièrement `bootstrap_all_agents`.

## Objectifs

1. **Reprise exacte et quasi instantanée** du plan 24h : zéro appel OTP, zéro appel LLM
   au démarrage quand un snapshot valide existe.
2. **Décisions LLM figées** : le plan rechargé doit reproduire les mêmes choix d'itinéraire
   que le run d'origine → simulation déterministe et reproductible.
3. **Invalidation par hash de population** : le snapshot n'est réutilisé que si la
   population (identités + activités + horaires) est inchangée.
4. **Dégradation propre** : snapshot absent/invalide ⇒ retomber sur le warm-up normal,
   sans erreur.
5. **Aucune régression** sur le chemin de dispatch existant (`_messages` → `publish_loop`).

## Hypothèses (périmètre actuel)

- **Météo et jour de démarrage sont en dur** → ils ne font **pas** partie de la clé
  d'invalidation pour l'instant. La clé est `hash(population)` **uniquement**.
- Conséquence assumée : si la météo, le jour de simulation, le modèle/prompt LLM ou
  les données GTFS changent **sans** modifier la population, le snapshot reste considéré
  valide et rejoue un plan potentiellement périmé. Cette extension (clé enrichie ou
  `cache_version` à bumper manuellement) est repoussée à un ticket ultérieur.
- L'`/init` se fait à `t0` : tous les agents sont *idle* (pas de plan en cours d'exécution),
  ce qui simplifie la ré-hydratation (pas d'état partiel mi-trajet à reconstituer).

## Existant réutilisable

- `world/population.py:132` `dump_population_snapshot()` : fait déjà `model_dump()` de la
  population **complète**, donc `state.precomputed_moves` (les `PersonMove` avec leur
  `TravelPlan`) sont **déjà sérialisés**. Le snapshot quotidien de 2h
  (`_write_population_checkpoint`, `simulation_controller.py:559`) s'appuie dessus.
- `world/population.py:150` `load_population_state()` : ne recharge aujourd'hui que les
  `scheduled_start_time` — à étendre (ou à doubler d'une fonction dédiée) pour ré-hydrater
  l'état complet.
- Le cache de routage persistant (`OtpPersistentCache`, activé par défaut depuis
  `config.yaml`) et le cache LLM sémantique (`LlmSemanticCache`, déterministe à mémoire
  froide) restent le **filet de secours** : si le snapshot est invalidé, le warm-up
  rejoué tape dans ces caches au lieu de refaire des appels réseau complets.

## Solution technique préconisée

### 1. Clé d'invalidation — `population_hash`

Calculer un SHA-256 sur la **population sérialisée d'entrée** (identités + activités +
horaires), **avant** enrichissement par les `precomputed_moves`, pour garantir la stabilité :

```python
def compute_population_hash(people: list[Person]) -> str:
    payload = [
        {
            "person_id": p.person_id,
            "activities": sorted(
                ({"id": a.id, "purpose": a.purpose,
                  "start_time": a.start_time, "end_time": a.end_time,
                  "location": a.location_key()}  # coords arrondies
                 for a in p.identity.activities),
                key=lambda a: (a["start_time"] or 0, a["id"]),
            ),
        }
        for p in sorted(people, key=lambda p: p.person_id)
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
```

### 2. Format du snapshot

Réutiliser `dump_population_snapshot`, en préfixant un en-tête de métadonnées :

```json
{
  "header": {
    "schema_version": 1,
    "population_hash": "<sha256>",
    "population_size": 1000,
    "sim_date": "2025-01-15",
    "created_at": "<iso8601>"
  },
  "people": [ /* model_dump() de chaque Person, dont state.precomputed_moves */ ]
}
```

Chemin : `settings.workdir / f"plan_snapshot_{population_size}.json"` (un fichier par
taille de population ; le `population_hash` dans l'en-tête tranche les collisions).

### 3. Écriture — fin du warm-up

À la fin de `bootstrap_all_agents`, après que toutes les files `precomputed_moves` sont
remplies, écrire le snapshot (atomique, via `os.replace` comme l'existant) avec le
`population_hash` courant dans l'en-tête.

### 4. Lecture — début de `/init`

Avant d'appeler `bootstrap_all_agents` :

```
header = lire_entete(plan_snapshot)
si header existe ET header.population_hash == compute_population_hash(population_courante):
    pour chaque Person du snapshot:
        ré-hydrater state.precomputed_moves (validation Pydantic deque[PersonMove])
        ré-hydrater le 1er move + scheduling (start_on_activity)
        pousser le 1er move dans self._messages (Action), comme le fait le bootstrap
    log "[init] plan rechargé depuis snapshot (hash match) — bootstrap sauté"
    return            # on saute entièrement bootstrap_all_agents
sinon:
    log "[init] snapshot absent/obsolète — warm-up complet"
    bootstrap_all_agents(...)   # qui réécrira le snapshot en fin de phase
```

### 5. Points de vigilance

- **Re-validation Pydantic** : confirmer que `deque[PersonMove]` et `TravelPlan` se
  rechargent proprement depuis le JSON `model_dump()` (types `deque`, timestamps, legs).
- **Cohérence du dispatch** : le 1er move rechargé doit suivre exactement le même chemin
  que le bootstrap (`Action(person_id, action=move.model_dump(exclude_none=False))` →
  `_messages` → `publish_loop`), pour ne pas diverger du comportement GAMA actuel.
- **Horizon glissant** : après rechargement, `precomputed_horizon_act` / `_ts` doivent être
  positionnés pour que `_refill_precomputed_queue` reparte correctement.
- **Atomicité / corruption** : un snapshot tronqué (kill en cours d'écriture) doit être
  détecté (JSON invalide / `schema_version` absent) et traité comme « pas de snapshot ».

## Fichiers concernés

- `llm-agents/world/population.py`
  - `dump_population_snapshot` : ajouter l'en-tête de métadonnées (ligne 132)
  - nouvelle `load_plan_snapshot(path) -> header|None` + ré-hydratation
  - nouvelle `compute_population_hash(people)`
- `llm-agents/urban_mobility_agents/simulation_controller.py`
  - `bootstrap_all_agents` (ligne 762) : court-circuit en lecture au début, écriture en fin
- `llm-agents/settings.py` : chemin/nom du fichier snapshot (sous `DataConfig`)

## Tests

- Run 1 (snapshot absent) → warm-up complet + snapshot écrit ; mesurer `agent_bootstrap_duration_seconds`.
- Run 2 (population identique) → snapshot rechargé, bootstrap sauté ; vérifier que les
  premiers moves dispatchés sont identiques au Run 1 et que la durée d'init s'effondre.
- Run 3 (population modifiée d'un agent) → hash différent → warm-up complet relancé.
- Snapshot corrompu → fallback warm-up sans crash.

## Priorité

Moyenne-haute — gain de temps de démarrage majeur sur les runs répétés à population
constante (itérations de dev, replays d'expérience), sans impact sur la dynamique de
simulation tant que la population ne change pas.

## Suites possibles (hors périmètre)

- Enrichir la clé d'invalidation (météo, jour de simulation, modèle/prompt LLM, version
  GTFS) ou introduire une `cache_version` à bumper manuellement.
- Versionner le snapshot via DVC pour le partager dans l'équipe (cf. Solution 3 écartée).
