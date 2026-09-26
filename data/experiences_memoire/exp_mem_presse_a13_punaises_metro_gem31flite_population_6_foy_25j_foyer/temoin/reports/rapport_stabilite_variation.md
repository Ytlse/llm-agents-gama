# Rapport d'Analyse Comportementale : Stabilité Modale et Taux de Variation

*Généré le 2026-09-26 00:59:57 par `modal_variation_rate.py`*

## 1. Synthèse Exécutive

Aucun événement dans ce run (bras témoin) : toutes les transitions sont en « Sans événement ».

### Chiffres clés par phase :

| Phase | Transitions | Taux Variation Modal | Stabilité Modale | Taux Variation Itinéraire | Stabilité Itinéraire |
|---|:---:|:---:|:---:|:---:|:---:|
| **Sans événement** | 403 | **11.4%** | 88.6% | 58.3% | 41.7% |

---

## 2. Rigidité vs Flexibilité par Activité (Motif)

| Motif | Transitions | Stabilité Globale | Taux Variation Avant | Taux Variation Après | Diagnostic |
|---|:---:|:---:|:---:|:---:|:---:|
| **leisure** | 55 | **100.0%** | N/A | N/A | `Très Rigide` |
| **Etude** | 37 | **94.6%** | N/A | N/A | `Très Rigide` |
| **other** | 56 | **85.7%** | N/A | N/A | `Modérée` |
| **Travail** | 74 | **79.7%** | N/A | N/A | `Modérée` |
| **home** | 112 | **75.9%** | N/A | N/A | `Modérée` |

- **La plus stable** : `leisure` — 100.0% de transitions sans changement de mode, sur 55.
- **La plus variable** : `home` — 24.1% de changements de mode, sur 112.

---

## 3. Analyse de l'Entropie Modale et Bouquet d'Itinéraires

L'entropie de Shannon $H(Persona) = - \sum p_m \log_2(p_m)$ quantifie la diversification du bouquet de choix : 0 bit traduit un seul mode ; « — » signale une phase sans trajet.

| Persona | Exposition | Trajets | Modes Distincts | Entropie H (bits) | Équitabilité Pielou | Entropie Avant | Entropie Après | Statut après |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1320713** | Sans événement | 95 | 3 | **1.332** | 0.574 | — | — | — |
| **1127258** | Sans événement | 76 | 2 | **1.000** | 0.431 | — | — | — |
| **1127260** | Sans événement | 40 | 2 | **0.881** | 0.380 | — | — | — |
| **1127257** | Sans événement | 59 | 2 | **0.818** | 0.352 | — | — | — |
| **1320712** | Sans événement | 59 | 3 | **0.480** | 0.207 | — | — | — |
| **1127259** | Sans événement | 96 | 1 | **0.000** | 0.000 | — | — | — |

---

## 4. Décomposition des Décisions

- **Volume total de décisions enregistrées :** 425
- **Délibérations LLM effectives :** 295 (69.4%)
- **Replis techniques d'urgence :** 0 (100% des décisions ont été délibérées ou contraintes par l'offre physique)
- **Choix physiquement contraints (un seul itinéraire disponible) :** 92 (21.6%)
- **Autres méthodes de sélection :** 38 (8.9%)
