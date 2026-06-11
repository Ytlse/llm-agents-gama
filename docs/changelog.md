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
