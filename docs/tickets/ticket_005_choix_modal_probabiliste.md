# Ticket 005 — Choix modal probabiliste : du mode choisi à la distribution tirée

## Description

Jusqu'à la bascule du 2026-07-29, le LLM **choisissait** l'itinéraire d'un persona
(`chosen_index`). À température 0, une même personne replacée dans le même contexte
reprenait donc systématiquement la même décision — et le cache sémantique figeait ce
choix pour tous les jours suivants. Un persona qui « hésite » entre voiture et bus
produisait 100 % de voiture : l'hésitation, pourtant l'information la plus utile pour
reconstituer une part modale, était perdue à l'écriture de la réponse.

Le prompt demande désormais une **probabilité par option** (somme = 100) et la décision
est un **tirage** dans cette distribution. Le socle est livré (cf. §« Livré ») ; ce ticket
couvre ce qui reste à faire pour que toute la chaîne — scoring de calibration, analyses,
dashboards — exploite la distribution au lieu de la subir.

**Insight qui structure le reste du travail** : une distribution contient strictement plus
d'information qu'un tirage. Partout où l'on ne cherche pas à simuler un individu mais à
**mesurer une population** (calibration, parts modales, dashboards), tirer puis compter
ré-introduit un bruit d'échantillonnage qu'on peut simplement ne pas payer — en sommant
les probabilités au lieu de compter des tirages.

## Objectifs

1. **Supprimer le bruit d'échantillonnage du scoring de calibration** : passer les
   métriques (L1, EMD, JSD) de comptages de décisions à des **comptages pondérés** par
   les probabilités. Une distribution 60/40 sur un persona doit produire exactement
   60/40, sans variance.
2. **Rendre la répartition attendue exploitable en analyse** : les scripts et notebooks
   qui lisent `moves.csv` doivent comparer part **attendue** et part **tirée**.
3. **Porter les notebooks d'expérimentation** encore écrits contre `chosen_index`.
4. **Observer la dérive** : un panneau Grafana « attendu vs tiré » ; un écart persistant
   entre les deux signale un biais dans le tirage ou dans le cache, pas dans le modèle.

## Livré (2026-07-29) — socle de la bascule

- **Schéma & prompts** : `probabilities: [{index, mode, probability}]` dans
  `llm_module/prompts/schemas.json` ; blocs « Instructions de sortie » réécrits dans les
  16 variantes de `prompts.yaml` ; consigne de sommation dans le template Jinja.
- **Post-traitement partagé** : `llm_module/core/mode_choice.py` — normalisation
  tolérante, `mode_distribution` (modes canoniques, **0 % pour un mode non proposé**),
  `draw_index` à graine dérivée de `(mode_draw_seed, agent, activité, jour simulé)`.
- **Décision & cache** : tirage côté simulation sur la liste triée par code de plan ; le
  cache Qdrant persiste la **distribution** et rejoue un tirage à chaque hit
  (renormalisation sur les options survivantes, repli pour les points hérités).
- **Traçabilité** : une colonne par mode dans `moves.csv` (`P(Marche) %`, …) ; compteur
  worker `llm_mode_probability_pct_total{mode}`.
- **Calibration** : `decisions_from_agents()` produit des décisions **pondérées** par les
  probabilités — aucun tirage, donc aucun bruit d'échantillonnage dans le score (éval
  `train` : 99 → 33 requêtes, et scores reproductibles au chiffre près).

## Reste à faire

### 1. ~~Comptages pondérés dans la calibration~~ — **livré (2026-07-29)**

`decisions_from_agents()` produit des décisions `(agent_id, mode, poids)` ; les métriques
somment les poids (`metrics.mode_counts`) au lieu de compter des lignes, et `n` reste un
effectif de **personas** (`metrics.stratum_size`). Le score d'un prompt est désormais
exact — deux évaluations donnent le même chiffre. `eval_samples` est sans objet et sort
de `eval_params_key()` (`policy=weighted`). Les décisions historiques (paires
`(agent_id, mode)`) sont relues avec un poids de 1 : le backtest reste exact.

### 2. ~~Scripts et notebooks~~ — **livré (2026-07-29)**

`run_report.py` compare part attendue et part tirée (+ alarme de dérive) ;
`scripts/analysis/mode_probabilities.py` et `scripts/models_influence/probability_compat.py`
portent la logique réutilisable ; les notebooks concernés sont patchés. ⚠ Les notebooks
n'ont **pas été exécutés** (ils appellent de vrais fournisseurs).

### 3. Fiabiliser l'étiquette de mode — **partiellement livré**

Chaque entrée `probabilities` porte le `mode` de l'option, recopié par le LLM. Ce champ a
un statut **asymétrique** : la production l'ignore (elle prend le mode des `legs` de
l'option, source de vérité), alors qu'en calibration il *est* la mesure — il alimente
`categorize_mode()` donc la loss. Il ne coûte rien là où il est inerte, et 60 tokens par
persona là où il est critique.

- ✅ **Contrôle d'intégrité** (livré) : comparer, dans le worker, l'étiquette annoncée et le mode réel
  de l'option (les deux sont déjà côte à côte). Un désaccord ne dit pas « libellé
  approximatif » mais « le modèle a confondu les options » — ses probabilités sont alors
  attribuées aux mauvais index, bug silencieux qui fausse toute la distribution.
- ✅ **Calibration déterministe** (livré) : les options de la section gelée sont parsées
  au chargement du dataset (`^- \[(\d+)\]\s+([^:]+):` — validé sur les 803 records de
  `v1`, 0 échec, indices contigus) ; le mode vient du record, plus de la réponse.
- ⬜ **Reste** : si le taux de désaccord mesuré s'avère nul, retirer `mode` du schéma —
  174 → 114 tokens de sortie par persona (mesure cl100k, 6 options).

### 4. ~~Observabilité~~ — **livré (2026-07-29)**

Row « Répartition attendue vs tirée » dans `grafana/dashboards/07_metier_mobilite.json` :
deux camemberts, l'écart en points, et le bandeau d'intégrité des étiquettes. Les deux
vocabulaires sont ramenés à un socle commun par `label_replace`. Documenté dans
`docs/arch/monitoring.md` (et non dans `docs/grafana_elements.md`, qui décrit
explicitement les dashboards d'avant la refonte du 2026-07-10).

## Validation à faire avant de lancer une campagne

- **Un appel réel par provider** : le nouveau schéma n'a jamais été soumis à un provider.
  Vérifier l'acceptation du `additionalProperties: false` imbriqué en mode Structured
  Output, et le respect de la consigne « une entrée par option ».
- **Budget de tokens de sortie** : la réponse passe d'un entier à un tableau de N objets
  (~25-40 tokens par option). Contrôler `max_tokens` (4096) et le dimensionnement des
  lots (`assumed_prompt_tokens`, prévention des HTTP 413) sur un lot plein.
- **Repeupler le cache LLM** : le répertoire de l'ancien checksum a été supprimé ; un run
  de peuplement est nécessaire avant les runs longs.

## Fichiers concernés

| Zone | Fichiers |
|---|---|
| Calibration (pondération) | `prompt_calibration/calibration/{evaluation,models,store,metrics,dashboard_data,dashboard,backtest,targeting,mutation,loop}.py` |
| Scripts | `scripts/debug/{run_report,quota_validator,llm_capacity}.py`, `scripts/analysis/*`, `scripts/models_influence/*`, `scripts/infra/test_boucle_comp.ipynb` |
| Observabilité | `grafana/dashboards/07_metier_mobilite.json`, `docs/grafana_elements.md` |
| Doc | `docs/arch/{llm-inference,cache-memory,prompt_calibration,monitoring}.md`, `prompt_calibration/docs/quotas-et-modeles.md` |

## Tests

- Métriques pondérées : une distribution 60/40 sur un persona donne exactement 60/40
  (aucune variance entre deux exécutions).
- Backtest : relecture d'un historique de décisions **non pondérées** sans régression.
- Non-régression de l'existant : `test_mode_choice.py` (normalisation, 0 % des modes
  absents, reproductibilité du tirage), `test_llm_cache_redraw.py` (retirage, options
  disparues), `test_move_logger_columns.py` (alignement en-têtes/valeurs).

## Priorité

**Reste ouvert** : la validation contre un vrai fournisseur (cf. section précédente) et
le retrait éventuel du champ `mode` du schéma. Tout le reste est livré.

## Risques / limites assumées

- **Invalidations déjà encaissées** : cache LLM (répertoire de l'ancien checksum
  supprimé) et évaluations de calibration payées (`node_hash` + `policy=draw`).
- **Le LLM peut mal sommer.** La normalisation renormalise et journalise ; un vecteur
  inexploitable retombe sur l'uniforme, ce qui est une décision *neutre*, pas une erreur
  visible. Surveiller le volume de ces avertissements sur les premiers runs.
- **Modes canoniques figés** (`CANONICAL_MODES`) : ajouter un mode de transport à la
  simulation impose de l'ajouter là **et** dans les colonnes de `moves.csv`.
- **La reproductibilité dépend de l'ordre trié par code de plan** : deux options de codes
  identiques (itinéraires jumeaux) collisionnent — sans effet sur la distribution, mais
  le tirage n'est alors pas discriminant entre elles.
