# Rapport d'Analyse Comportementale : Stabilité Modale et Taux de Variation

*Généré le 2026-09-25 21:50:25 par `modal_variation_rate.py`*

## 1. Synthèse Exécutive

Événement du run : **a13_punaises_metro — Bed bug scare on the metro**. Les phases sont lues foyer par foyer dans `evenements.jsonl` et la population du run ; les agents qu'aucune exposition n'a touchés, ni eux ni leur foyer, sont rangés à part (« Hors foyer exposé »).

- `a13_punaises_metro`, foyer 534995 : 2026-03-27 — 1127257 (co_resident), 1127258 (co_resident), 1127259 (co_resident), 1127260 (expose)
- `a13_punaises_metro`, foyer 643030 : 2026-03-27 — 1320712 (co_resident), 1320713 (expose)

### Chiffres clés par phase :

| Phase | Transitions | Taux Variation Modal | Stabilité Modale | Taux Variation Itinéraire | Stabilité Itinéraire |
|---|:---:|:---:|:---:|:---:|:---:|
| **1. Avant l'événement** | 176 | **15.9%** | 84.1% | 55.1% | 44.9% |
| **2. Jour(s) de l'événement** | 21 | **9.5%** | 90.5% | 57.1% | 42.9% |
| **3. Après l'événement** | 211 | **8.1%** | 91.9% | 55.5% | 44.5% |

---

## 2. Rigidité vs Flexibilité par Activité (Motif)

| Motif | Transitions | Stabilité Globale | Taux Variation Avant | Taux Variation Après | Diagnostic |
|---|:---:|:---:|:---:|:---:|:---:|
| **Etude** | 38 | **100.0%** | 0.0% | 0.0% | `Très Rigide` |
| **leisure** | 55 | **96.4%** | 0.0% | 7.1% | `Très Rigide` |
| **other** | 57 | **86.0%** | 25.0% | 6.7% | `Modérée` |
| **Travail** | 76 | **79.0%** | 28.1% | 15.0% | `Modérée` |
| **home** | 113 | **77.9%** | 30.6% | 15.5% | `Modérée` |

- **La plus stable** : `Etude` — 100.0% de transitions sans changement de mode, sur 38.
- **La plus variable** : `home` — 22.1% de changements de mode, sur 113.

---

## 3. Analyse de l'Entropie Modale et Bouquet d'Itinéraires

L'entropie de Shannon $H(Persona) = - \sum p_m \log_2(p_m)$ quantifie la diversification du bouquet de choix : 0 bit traduit un seul mode ; « — » signale une phase sans trajet.

| Persona | Exposition | Trajets | Modes Distincts | Entropie H (bits) | Équitabilité Pielou | Entropie Avant | Entropie Après | Statut après |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1320713** | foyer exposé | 97 | 3 | **1.415** | 0.610 | 0.997 | 1.564 | Multimodal |
| **1127258** | foyer exposé | 78 | 2 | **1.000** | 0.430 | 1.000 | 1.000 | Multimodal |
| **1127260** | foyer exposé | 40 | 2 | **0.993** | 0.428 | 0.918 | 0.722 | Multimodal |
| **1127257** | foyer exposé | 59 | 2 | **0.887** | 0.382 | 0.877 | 0.894 | Multimodal |
| **1320712** | foyer exposé | 59 | 3 | **0.480** | 0.207 | 0.825 | 0.000 | Un seul mode (0 bit) |
| **1127259** | foyer exposé | 97 | 1 | **0.000** | 0.000 | 0.000 | 0.000 | Un seul mode (0 bit) |

---

## 4. Décomposition des Décisions

- **Volume total de décisions enregistrées :** 430
- **Délibérations LLM effectives :** 291 (67.7%)
- **Replis techniques d'urgence (erreurs / index par défaut) :** 3 (0.7%)
  > [!NOTE]
  > **Avertissement méthodologique :** 3 choix ont été forcés par repli technique automatique (ex. quota d'API épuisé, indisponibilité de passerelle). Ces replis ne reflètent pas un arbitrage de l'agent et doivent être dissociés de l'effet de l'événement.
- **Choix physiquement contraints (un seul itinéraire disponible) :** 98 (22.8%)
- **Autres méthodes de sélection :** 38 (8.8%)
