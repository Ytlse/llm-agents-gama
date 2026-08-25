# Run de référence — les corrections mesurées sur jeux gelés, implémentées en dur et rejouées sur GAMA

Mesure du **2026-08-25**, portant sur le run GAMA `2026-08-24_17_34` (1 000 agents, journée
du 16 mars 2026 simulée, reprise à chaud sur un second jour).

**Verdict : ADOPTÉ comme référence.** Le run devient le substrat épinglé de la page de
synthèse (`scripts/synthesis/sources.yaml`) et la source des jeux gelés `v9`.

⚠ **Support : un RUN, pas un jeu gelé.** Les autres traces de ce dossier scorent des jeux
gelés — mêmes personas, mêmes options des deux côtés, une seule variable qui bouge. Celle-ci
compare **deux runs complets** : c'est une mesure de production, pas une mesure appariée, et
son écart n'est pas attribuable à une cause unique. La section « Ce que ce chiffre ne dit
pas » ci-dessous n'est pas une précaution de style, c'est la limite du dispositif.

## Ce qui a été comparé

| | Référence | Ce run |
|---|---|---|
| Run | `2026-08-02_18_55` | `2026-08-24_17_34` |
| Décisions scorées | 2 830 (867 personnes) | 2 911 (890 personnes) |
| Composite `emd_jsd` | 20,11 | **18,23** |
| L1 global | 33,27 pt | **29,81 pt** |

Parts modales (masse de probabilité, quatre modes renormalisés) :

| | marche | voiture | vélo | TC |
|---|---|---|---|---|
| Référence `2026-08-02` | 10,17 | 56,87 | 16,11 | 16,85 |
| **Ce run** | **11,90** | **57,58** | **13,29** | **17,23** |
| Cible EMC² 2023 | 26,80 | 56,70 | 4,12 | 12,37 |

## Ce qui a changé entre les deux runs

Relevé par comparaison des `static_config.yaml` et des en-têtes de `moves.csv` des deux runs,
et non d'après le journal des changements — ce qui compte ici est ce que le run a réellement
porté :

- **Anticipation de la journée** (`agenda_anticipation_enabled: true`) — colonne
  `Anticipation` nouvelle dans le journal : 2 658 décisions annotées `agenda`, 707 `meteo`.
- **Mémoïsation des réflexions** (`reflection_memo_enabled: true`).
- **Temps terminal des itinéraires** aligné sur EMC² (voiture et vélo, production `tt3` —
  mesuré à part sur jeu gelé, cf. `2026-08-24_temps_terminal`).
- **Règle de chaîne au prompt système** (variante `expert_chaine`) — mesurée à part, sans
  gain (`+0,21` composite), et conservée pour d'autres raisons.
- **Disjoncteur du gateway LLM** (`remote_llm_circuit_failure_threshold: 10`,
  `remote_llm_circuit_probe_interval: 60`) — il a joué 23 fois pendant ce run.
- **Flotte de modèles remaniée** : `groq_llama3`/`groq_llama31` retirés,
  `groq_qwen_qwen3_6_27b` et quatre entrées Gemini ajoutées.

La chaîne de véhicules et le type de logement étaient **déjà** présents au 2 août : ils ne
font pas partie de l'écart.

## Ce que ce chiffre ne dit pas

1. **L'écart de −1,88 n'est pas attribuable.** Plusieurs changements sont simultanés, et la
   composition des modèles diffère fortement : 96,4 % des décisions LLM de ce run viennent
   des deux Gemini, contre 77,9 % dans la référence, où Cerebras portait 352 décisions. Un run
   n'isole aucune variable — c'est précisément pourquoi les corrections se mesurent sur jeux
   gelés, et pourquoi cette ligne ne remplace aucune de ces mesures.
2. **Le bruit de découpage vaut 5,41 points d'amplitude** sur ce run (60 tirages), soit
   presque trois fois l'écart mesuré. Le gain est réel sur la loss ; sa marge ne l'est pas.
3. **11,4 % des décisions du jour simulé sont des replis d'erreur** (390 sur 3 421) : le
   modèle n'a pas répondu, le contrôleur a pris l'itinéraire d'index 0. Elles sont exclues du
   score — il n'y a pas de choix à noter — **mais la simulation les a jouées**. Cause :
   690 erreurs LLM, dont 668 en `402 Payment required` — Mistral 239, Cerebras 429 sur ses
   deux entrées (crédits épuisés, pas un dépassement de cadence).
4. **L'agrégat est meilleur que chacune de ses parties, par compensation d'erreurs.** Les
   décisions d'un modèle scorent 19,01 et les itinéraires uniques 104,47, mais le run entier
   18,23 : les premières sur-représentent les transports collectifs (23,8 % contre 12,4 %
   attendus), les secondes n'en produisent **aucun** (0,0 %, 76,6 % de voiture). Les deux
   biais s'annulent dans la moyenne. Un score de run agrégé peut donc s'améliorer sans
   qu'aucune de ses composantes ne s'améliore : à ne jamais lire seul.
5. **Les deux Gemini ne se séparent pas.** `gemini-3.1-flash-lite-preview` score 18,10 et
   `gemini-3.5-flash-lite` 19,19, mais le test de permutation rend **p = 0,63** sur 60
   tirages : l'écart est indiscernable du découpage.

## Ce que le run a produit en aval

- Substrat épinglé de la page de synthèse — `scripts/synthesis/sources.yaml`.
- Volet 3 (modèle PROGEDO) recalculé sur ce run : `make common-set-predict`, 2 911 décisions,
  100 % scorées.
- Jeux gelés **`v9`** (amendement A10 du protocole) : `train` 431 personas / 1 294 décisions,
  `val` 182 / 516, `test` 258 / 723, `screen` 121 / 341.

Le volet 2 (prompts ré-évalués sur le jeu commun) reste **non mesuré** sur ce substrat : la
page l'affiche en « Données manquantes » plutôt que de servir la mesure faite sur le run
précédent.

## Reproduire

```bash
make synthesis                                  # page épinglée sur ce run
make model-compare RUN=experiments/archive/2026-08-24_17_34 \
     BASELINE="experiments/archive/2026-08-02_18_55"
```

Chiffres de cette trace : `results.json`, extrait de
`docs/synthesis/models/2026-08-24_17_34/data.json` — aucun nombre recopié à la main.
Empreinte du journal mesuré (`moves.csv`) :
`1d217aed2a503dc21c4c4cc2dd737ac902d60f529480cb20e416abad3a8bbb00`.
