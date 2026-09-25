# Rapport d'Analyse Comportementale : Stabilité Modale et Taux de Variation

*Généré le 2026-09-25 15:14:49 par `modal_variation_rate.py`*

## 1. Synthèse Exécutive

Aucun événement dans ce run (bras témoin) : toutes les transitions sont en « Sans événement ».

### Chiffres clés par phase :

| Phase | Transitions | Taux Variation Modal | Stabilité Modale | Taux Variation Itinéraire | Stabilité Itinéraire |
|---|:---:|:---:|:---:|:---:|:---:|
| **Sans événement** | 138 | **31.2%** | 68.8% | 72.5% | 27.5% |

---

## 2. Rigidité vs Flexibilité par Activité (Motif)

| Motif | Transitions | Stabilité Globale | Taux Variation Avant | Taux Variation Après | Diagnostic |
|---|:---:|:---:|:---:|:---:|:---:|
| **Travail** | 22 | **100.0%** | N/A | N/A | `Très Rigide` |
| **Etude** | 22 | **81.8%** | N/A | N/A | `Modérée` |
| **home** | 43 | **69.8%** | N/A | N/A | `Flexible` |
| **Achats** | 11 | **36.4%** | N/A | N/A | `Flexible` |
| **other** | 10 | **30.0%** | N/A | N/A | `Flexible` |

- **La plus stable** : `Travail` — 100.0% de transitions sans changement de mode, sur 22.
- **La plus variable** : `other` — 70.0% de changements de mode, sur 10.

---

## 3. Analyse de l'Entropie Modale et Bouquet d'Itinéraires

L'entropie de Shannon $H(Persona) = - \sum p_m \log_2(p_m)$ quantifie la diversification du bouquet de choix : 0 bit traduit un seul mode ; « — » signale une phase sans trajet.

| Persona | Exposition | Trajets | Modes Distincts | Entropie H (bits) | Équitabilité Pielou | Entropie Avant | Entropie Après | Statut après |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **286921** | Sans événement | 57 | 3 | **1.306** | 0.562 | — | — | — |
| **286923** | Sans événement | 46 | 3 | **1.192** | 0.513 | — | — | — |
| **286922** | Sans événement | 24 | 3 | **0.497** | 0.214 | — | — | — |
| **286920** | Sans événement | 24 | 1 | **0.000** | 0.000 | — | — | — |

---

## 4. Décomposition des Décisions

- **Volume total de décisions enregistrées :** 151
- **Délibérations LLM effectives :** 132 (87.4%)
- **Replis techniques d'urgence :** 0 (100% des décisions ont été délibérées ou contraintes par l'offre physique)
- **Choix physiquement contraints (un seul itinéraire disponible) :** 19 (12.6%)
