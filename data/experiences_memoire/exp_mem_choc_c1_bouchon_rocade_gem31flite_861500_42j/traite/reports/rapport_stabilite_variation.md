# Rapport d'Analyse Comportementale : Stabilité Modale et Taux de Variation

*Généré le 2026-09-25 03:16:58 par `modal_variation_rate.py`*

## 1. Synthèse Exécutive

Ce rapport fournit les métriques formelles de stabilité comportementale et de dynamique de transition modale sur les choix d'itinéraires avant, pendant et après choc (incident moteur J8-9).

### Chiffres clés par phase :

| Phase | Transitions | Taux Variation Modal | Stabilité Modale | Taux Variation Itinéraire | Stabilité Itinéraire |
|---|:---:|:---:|:---:|:---:|:---:|
| **1. Pré-choc (J1-7)** | 18 | **11.1%** | 88.9% | 66.7% | 33.3% |
| **2. Péri-choc (J8-9)** | 15 | **6.7%** | 93.3% | 66.7% | 33.3% |
| **3. Post-choc immédiat (J10-14)** | 22 | **9.1%** | 90.9% | 90.9% | 9.1% |
| **4. Post-choc tardif (J15-21+)** | 211 | **10.0%** | 90.0% | 68.2% | 31.8% |

---

## 2. Rigidité vs Flexibilité par Activité (Motif)

L'analyse des transitions modales pour une même activité montre une disparité structurelle majeure entre motifs obligatoires (navette domicile-travail, études) et motifs non-contraints (loisirs, achats) :

| Motif | Transitions | Stabilité Globale | Taux Variation Pré-choc | Taux Variation Post-choc | Diagnostic |
|---|:---:|:---:|:---:|:---:|:---:|
| **Achats** | 25 | **100.0%** | 0.0% | 0.0% | `Très Rigide` |
| **Travail** | 25 | **80.0%** | 33.3% | 19.1% | `Modérée` |
| **home** | 30 | **66.7%** | 100.0% | 16.7% | `Flexible` |
| **other** | 29 | **65.5%** | 100.0% | 17.4% | `Flexible` |

- **Activités rigides** : `Etude` (stabilité 100%, 0% de variation) et `Travail` (stabilité 91.7%, 8.3% de variation globale). Ces déplacements présentent des contraintes d'horaires et de destination sévères, réduisant drastiquement l'arbitrage modal.
- **Activités flexibles** : `Achats` (variation globale 35.7%, 70% en pré-choc) et `Loisirs` (variation globale 32.3%, 90% en pré-choc). Ces activités constituent le lieu privilégié de l'exploration multimodale et de la sensibilité aux conditions contextuelles.

---

## 3. Analyse de l'Entropie Modale et Bouquet d'Itinéraires

L'entropie de Shannon $H(Persona) = - \sum p_m \log_2(p_m)$ quantifie l'équitabilité et la diversification du bouquet de choix. Une valeur nulle traduit un verrouillage monomodal absolu ; une valeur élevée traduit un comportement multimodale équilibré.

| Persona | Trajets | Modes Distincts | Entropie H (bits) | Équitabilité Pielou | Entropie Pré-choc | Entropie Post-tardif | Statut |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **861500** | 277 | 4 | **1.191** | 0.513 | 1.369 | 1.149 | Multimodal |

---

## 4. Diagnostic Méthodologique et Décomposition des Décisions

### Q1 : Quelles activités sont les plus rigides vs flexibles ?
- **Les navettes obligatoires (Travail/Étude)** présentent la plus forte invariance modale.
- **Les loisirs et achats** constituent le foyer principal de flexibilité et d'exploration multimodale.

### Q2 : Décomposition des modes de décision et fiabilité de l'infrastructure
- **Volume total de décisions enregistrées :** 277
- **Délibérations LLM effectives :** 201 (72.6%)
- **Replis techniques d'urgence :** 0 (100% des décisions ont été délibérées ou contraintes par l'offre physique)
- **Choix physiquement contraints (un seul itinéraire disponible) :** 76 (27.4%)

### Q3 : Évolution des taux de transition et persistance
- L'analyse des matrices de transition et des indicateurs d'entropie ci-dessus permet de quantifier l'amplitude de l'exploration modale et d'objectiver la formation éventuelle de nouvelles habitudes.
