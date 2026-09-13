# Questions vivantes — onglet « Mes travaux » du Pilotage

Avancé sous hypothèses (cf. règle « questions vivantes »). À trancher.

## 1. Champs `provider` / `instance` / `batch_size` non vérifiés
`execution.yaml` ne porte pas ces champs (ou une sémantique divergente : le run expose
`regime_applique.parallelisme`, pas le `max_parallel_requests` de la fiche).

**Hypothèse retenue :** on ne compare QUE `model`, `temperature`, `seed` (présents et
sans ambiguïté dans le run). `provider`, `instance`, `batch_size`, `max_parallel_requests`
sont affichés en info, marqués « non vérifiés ».

**Alternative :** dériver `provider` du préfixe du modèle, mapper `max_parallel_requests`
sur `regime_applique.parallelisme`. Non fait : mapping fragile, risque de faux écarts.

## 2. « Écraser » = réécrire `experiments.yaml`
La source canonique du plan est `experiments.yaml` (l'HTML est désormais
`experiments_OLD_TO_DELETE.html`). Écraser un champ écrit dans la fiche du YAML,
en round-trip ruamel (diff limité à la seule ligne modifiée).

**À confirmer :** OK d'écrire dans le YAML canonique depuis le tableau de bord ?

## 3. Portée — TRANCHÉ (2026-09-07)
La fiche Gemini 3.5 Flash-Lite (`exp_01d_bare_gemini35_flash_lite`) a été **ajoutée au
YAML canonique** en Phase 1 (instance `google_gemini35`). Le plan compte 30 fiches.
Le ➕ reste disponible pour des blocs libres par phase.
