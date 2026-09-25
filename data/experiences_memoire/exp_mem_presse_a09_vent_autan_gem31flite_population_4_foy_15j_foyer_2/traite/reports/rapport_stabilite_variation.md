# Rapport d'Analyse Comportementale : Stabilité Modale et Taux de Variation

*Généré le 2026-09-25 14:09:30 par `modal_variation_rate.py`*

## 1. Synthèse Exécutive

Événement du run : **a09_vent_autan — Autan gales, parks closed**. Les phases sont lues foyer par foyer dans `evenements.jsonl` et la population du run ; les agents qu'aucune exposition n'a touchés, ni eux ni leur foyer, sont rangés à part (« Hors foyer exposé »).

- `a09_vent_autan`, foyer 133048 : 2026-03-26 — 286920 (expose), 286921 (co_resident), 286922 (co_resident), 286923 (co_resident)

### Chiffres clés par phase :

| Phase | Transitions | Taux Variation Modal | Stabilité Modale | Taux Variation Itinéraire | Stabilité Itinéraire |
|---|:---:|:---:|:---:|:---:|:---:|
| **1. Avant l'événement** | 91 | **35.2%** | 64.8% | 75.8% | 24.2% |
| **2. Jour(s) de l'événement** | 13 | **7.7%** | 92.3% | 61.5% | 38.5% |
| **3. Après l'événement** | 34 | **23.5%** | 76.5% | 64.7% | 35.3% |

---

## 2. Rigidité vs Flexibilité par Activité (Motif)

| Motif | Transitions | Stabilité Globale | Taux Variation Avant | Taux Variation Après | Diagnostic |
|---|:---:|:---:|:---:|:---:|:---:|
| **Travail** | 22 | **100.0%** | 0.0% | 0.0% | `Très Rigide` |
| **Etude** | 22 | **81.8%** | 28.6% | 0.0% | `Modérée` |
| **home** | 43 | **72.1%** | 32.1% | 27.3% | `Modérée` |
| **other** | 10 | **40.0%** | 71.4% | 50.0% | `Flexible` |
| **Achats** | 11 | **36.4%** | 71.4% | 66.7% | `Flexible` |

- **La plus stable** : `Travail` — 100.0% de transitions sans changement de mode, sur 22.
- **La plus variable** : `Achats` — 63.6% de changements de mode, sur 11.

---

## 3. Analyse de l'Entropie Modale et Bouquet d'Itinéraires

L'entropie de Shannon $H(Persona) = - \sum p_m \log_2(p_m)$ quantifie la diversification du bouquet de choix : 0 bit traduit un seul mode ; « — » signale une phase sans trajet.

| Persona | Exposition | Trajets | Modes Distincts | Entropie H (bits) | Équitabilité Pielou | Entropie Avant | Entropie Après | Statut après |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **286921** | foyer exposé | 57 | 3 | **1.350** | 0.581 | 1.318 | 1.483 | Multimodal |
| **286923** | foyer exposé | 46 | 3 | **1.126** | 0.485 | 1.151 | 0.469 | Multimodal |
| **286922** | foyer exposé | 24 | 3 | **0.497** | 0.214 | 0.669 | 0.000 | Un seul mode (0 bit) |
| **286920** | foyer exposé | 24 | 1 | **0.000** | 0.000 | 0.000 | 0.000 | Un seul mode (0 bit) |

---

## 4. Décomposition des Décisions

- **Volume total de décisions enregistrées :** 151
- **Délibérations LLM effectives :** 133 (88.1%)
- **Replis techniques d'urgence :** 0 (100% des décisions ont été délibérées ou contraintes par l'offre physique)
- **Choix physiquement contraints (un seul itinéraire disponible) :** 18 (11.9%)
