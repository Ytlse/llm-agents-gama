# Spécification — Racing ciblé par strate (successive halving)

**Statut :** ✅ **implémenté** (phase 4.6, désactivé par défaut : `racing_enabled: false`).
Extension de l'entonnoir multi-candidats (phase 4) de `prompt_calibration/`.
Voir la description de référence dans `docs/arch/prompt_calibration.md` §2.4.1 et les
tests dans `calibration/tests/test_loop.py` (`test_racing_*`). Ce document conserve la
spécification d'origine.

**Contexte du code :** `calibration/loop.py::CalibrationLoop._select_candidate`,
`calibration/mutation.py::build_mutation_user_msg`, `calibration/metrics.py::worst_strata_modes`,
`calibration/stats.py::bootstrap_delta`, `calibration/evaluation.py::Evaluator.evaluate`.

---

## 1. Problème

Aujourd'hui, à chaque itération, l'entonnoir fait (dans `_select_candidate`) :

1. bandit → `propose_candidates(k)` (le mutateur propose `k` mutations) ;
2. filtre tabu + validité + **diversité de bloc** (un candidat par bloc réellement modifié) ;
3. **screening one-shot** : chaque survivant est évalué **une fois** sur ~20 % du train
   (`screen_records`), le meilleur composite passe à l'éval complète ;
4. le gagnant unique suit la boucle normale (accept/reject, tabu, bandit, snippets).

Deux limites :

- **Screening one-shot** = une seule mesure bruitée décide du gagnant. Sur un petit
  jeu, un bon candidat peut perdre par malchance, et on ne réinvestit jamais de budget
  sur les candidats prometteurs mais incertains.
- **Aucun ciblage des strates en échec.** Les pires écarts sont concentrés sur quelques
  strates (ex. `genre[femme] × marche` sous-représenté de −20 pts). Le screening juge
  sur le composite global : un candidat qui corrige justement ces strates n'est pas
  favorisé, et on dépense autant de budget sur des strates déjà correctes.

## 2. Idée

Remplacer le screening one-shot par un **racing multi-tours (successive halving)**
précédé d'un **gate sur la strate la plus mal représentée** :

- **Gate strate (tour 0)** : d'abord évaluer les candidats **uniquement** sur les
  agents de la strate cible ; éliminer ceux qui n'améliorent pas son écart. Auto-arrêt
  bon marché : inutile de payer le reste de l'échantillon pour un candidat qui ne bouge
  pas la strate visée.
- **Racing (tours suivants)** : évaluer les survivants sur une fraction **croissante**
  du train ; à chaque palier, garder la meilleure moitié. On concentre le budget sur
  les candidats qui tiennent, on finit la mesure fine sur le plus prometteur.

## 3. Ce que ça change (et ne change pas) — à assumer

- **Ce n'est pas « le même résultat, juste priorisé ».** Le racing est une
  **approximation** : on classe sur des sous-échantillons bruités, donc on peut éliminer
  un candidat qui aurait gagné sur le train complet. → **garde-fou statistique**
  obligatoire (ne pas éliminer deux candidats dont les IC bootstrap se chevauchent).
- **Le gate strate change l'objectif local** : un candidat qui améliore le global mais
  pas la strate cible est rejeté au tour 0. C'est **voulu** (on attaque la pire strate),
  mais ça peut ralentir la baisse du composite global. → gate **périodique**
  (`racing_target_every`), pas systématique ; et **repli global** si le gate vide la liste.
- **Le cache amortit tout.** Chaque palier passe par `Evaluator.evaluate` → toute
  coalition/prompt déjà vu (run précédent, palier antérieur) est servi par le store
  content-addressed : le racing ne « repaie » pas l'historique.

## 4. Configuration (`RunConfig`, désactivé par défaut)

```python
racing_enabled: bool = False
racing_rungs: list[float] = [0.15, 0.35, 0.70, 1.0]  # fractions cumulées du train, croissantes
racing_keep_frac: float = 0.5                        # part conservée à chaque palier (≥ 1 candidat)
racing_target_gate: bool = True                      # tour 0 = strate la plus mal représentée
racing_target_every: int = 2                         # 1 itération sur N en mode ciblé (sinon global)
racing_min_gap: float = 1.0                          # ne pas éliminer si écart composite < ce seuil
```

## 5. Algorithme (remplace le bloc « 2. Screening » de `_select_candidate`)

Entrée : `survivors` (candidats ayant passé tabu + validité + diversité de bloc).

1. **Diversité en amont** (déjà partiellement là) : demander `k` candidats sur des
   **blocs distincts**. `build_mutation_user_msg` reçoit déjà la consigne « chaque
   candidat sur un bloc-cible DIFFÉRENT » + la liste des blocs récemment modifiés
   (`_recent_blocks`). Le filtre `rejected_dup_block` garantit l'unicité côté code.

2. **Gate strate** — si `racing_enabled and racing_target_gate and i % racing_target_every == 0` :
   - `row = worst_strata_modes(sa_df, cerema)[0]` → `(dim, cat, mode, diff, n)`
     (ex. `dim='genre', cat='femme'`).
   - `sub = _stratum_records(records, dim, cat)` — sous-ensemble des `records` de la
     strate (filtre sur `age_cat/occupation/genre/motif/dist_cat`, colonnes exposées
     par `evaluation.py`). Si `len(sub)` trop faible (< `racing_min_n`, à définir),
     **sauter le gate** (bruit trop élevé) et passer en racing global.
   - évaluer chaque candidat sur `sub` ; **éliminer** ceux dont l'écart de la strate ne
     s'améliore pas vs. `sa`. Si **tous** échouent → **repli global** (ne pas bloquer
     l'itération : on garde tous les survivants et on passe au racing global).

3. **Racing (successive halving)** sur les survivants restants :
   ```
   pour chaque fraction f de racing_rungs (croissante) :
       éval de chaque candidat survivant sur les f·|train| premiers records
       trier par composite croissant (plus bas = mieux)
       garder ceil(racing_keep_frac · n) candidats,
         MAIS ne jamais éliminer un candidat à moins de racing_min_gap
         du dernier gardé (ou si IC bootstrap chevauchant — bootstrap_delta)
       si un seul survivant → stop
   ```

4. **Gagnant** = unique survivant du dernier palier → `_record(best_cand, "proposed")`
   puis suite de boucle inchangée.

**Nouveaux verdicts persistés** (comme `rejected_dup_block`) : `rejected_gate`
(éliminé au gate strate), `rejected_race` (éliminé en cours de racing) — visibles au
dashboard, utiles au diagnostic.

## 6. Points d'ancrage précis

| Quoi | Où |
|---|---|
| Remplacer le screening one-shot | `loop.py::_select_candidate`, bloc « 2. Screening » |
| Filtre strate sur les records | nouvelle fonction `loop.py::_stratum_records(records, dim, cat)` près de `_sa_df` |
| Strate cible | `metrics.worst_strata_modes` (déjà utilisée dans `build_mutation_user_msg`) |
| Garde-fou statistique | `stats.bootstrap_delta` (déjà importé dans `loop.py`) |
| Évals par palier (avec cache) | `Evaluator.evaluate(node, applied, dataset, sub)` |
| Consigne de diversité | `mutation.build_mutation_user_msg` (`_recent_blocks`, déjà en place) |

## 7. Tests (obligatoire — règle étape 3)

Dans `calibration/tests/test_loop.py` :

- **gate** : un candidat qui n'améliore pas la strate cible est éliminé (`rejected_gate`) ;
- **repli global** : si le gate vide la liste, on ne bloque pas l'itération (tous repassent en racing) ;
- **garde-fou** : deux candidats à moins de `racing_min_gap` ne sont pas départagés (aucun `rejected_race`) ;
- **halving** : à chaque palier la taille du jeu d'éval croît et le nombre de survivants décroît ;
- **invariance** : `racing_enabled=False` → chemin actuel strictement inchangé (screening one-shot).

## 8. Mesure de succès

À budget d'éval égal, sur une campagne :

- **diversité des `target_block`** (doit monter — corrige « toujours le même bullet ») ;
- **vitesse de réduction de l'écart sur les strates ciblées** (le levier `worst_strata`) ;
- pas de régression du composite global final vs. l'entonnoir one-shot.
