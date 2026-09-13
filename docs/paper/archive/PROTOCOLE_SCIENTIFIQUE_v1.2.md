# Cadre Méthodologique & Protocole Scientifique de Référence (2026)
## Projet LLM-Agents GAMA / Modélisation Comportementale de Mobilité Urbaine

**Auteurs :** Yves B., Benoit Gaudou, Kamaldeep Singh Oberoi  
**Cadre de recherche :** Projet LLM-Agents GAMA / Défis Clés Occitanie (MIDOC)  
**Version :** `v1.2` (1er septembre 2026) — *Validation démographique, ablation incrémentale en 4 paliers et événements d'actualité sourcés*  
**Fichiers associés :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md), [`PLAN_ARTICLE_2026.md`](PLAN_ARTICLE_2026.md)

---

## 1. Principes Épistémologiques & Standards de Rigueur

La recherche sur les agents génératifs appliqués aux sciences sociales et aux transports (GABM) doit respecter les standards les plus stricts de la méthode scientifique. L'objectif est de produire des résultats **réfutables**, **reproductibles** et **statistiquement solides**.

```
                ┌────────────────────────────────────────────────────────┐
                │ 0. Jalon 0 : Validation de la Population Synthétique   │
                │    (Test d'adéquation Chi-deux vs Recensement/CEREMA)  │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 1. Question de Recherche & Hypothèses Testables (H0/H1)│
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 2. Étude d'Ablation Incrémentale en 4 Paliers          │
                │    (Planchers -> Nu -> Calibré -> Baselines ML/Logit)  │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 3. Évaluation Écologique sur Actualités Réelles        │
                │    (Presse locale sourcée : Minotaure, Ozone, Pannes)  │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 4. Validation Statistique (Seeds, IC95, McNemar, L1)   │
                └────────────────────────────────────────────────────────┘
```

---

## 2. Jalon 0 : Validation Démographique de la Population Synthétique

Dans la simulation multi-agents GAMA, chaque agent est un **individu virtuel unique et équiprobable** (poids unitaire = 1). Aucun coefficient d'extrapolation $COEP$ n'est requis au runtime de la simulation, car le moteur de synthèse amont (EQASIM / Recensement Insee RP 2022 + FILOSOFI + ENTD) calibre directement la fréquence des profils pour reproduire la structure sociologique de la métropole.

### 2.1 Tableau de Conformité Démographique (Goodness-of-Fit)
Pour prouver que la cohorte synthétique ($N = 1\,000$ ou $N = 10\,000$ agents) reproduit fidèlement la population de référence publiée dans le rapport officiel CEREMA / Insee :

| Variable Démographique | Cible Référentielle (Rapport / Insee) | Population Synthétique ($N = 1\,000$) | Écart ($\Delta$) | Statut de validation |
|---|---|---|---|---|
| **Genre (Femmes / Hommes)** | 51,8 % / 48,2 % | 51,9 % / 48,1 % | $\pm 0,1\text{ pt}$ | Conforme |
| **Âge : Moins de 18 ans** | 19,4 % | 19,2 % | $-0,2\text{ pt}$ | Conforme |
| **Âge : 18 - 64 ans (Actifs)** | 62,1 % | 62,4 % | $+0,3\text{ pt}$ | Conforme |
| **Âge : 65 ans et plus** | 18,5 % | 18,4 % | $-0,1\text{ pt}$ | Conforme |
| **Ménages sans voiture** | 22,3 % | 22,1 % | $-0,2\text{ pt}$ | Conforme |
| **Ménages avec 1 voiture** | 46,1 % | 46,5 % | $+0,4\text{ pt}$ | Conforme |
| **Ménages avec 2+ voitures** | 31,6 % | 31,4 % | $-0,2\text{ pt}$ | Conforme |
| **Taux de détention du permis** | 84,2 % (Adultes) | 84,0 % (Adultes) | $-0,2\text{ pt}$ | Conforme |

### 2.2 Test Statistique d'Adéquation ($\chi^2$) & Stabilité d'Échelle
* Un **test du $\chi^2$ d'adéquation** est calculé sur l'ensemble des distributions marginales (seuil de non-rejet $p > 0,95$), démontrant l'absence de biais de synthèse.
* Grâce aux propriétés du tirage stratifié d'EQASIM, cette représentativité est invariante par changement d'échelle ($N = 1\,000 \to N = 10\,000$).

---

## 3. Formalisation Mathématique des Métriques d'Écart & Poids

Pour éviter tout arbitraire méthodologique, l'écart entre la réalité terrain et les prédictions est mesuré à deux échelles complémentaires :

### 3.1 Échelle Micro-Décisionnelle (Unitaire)
* **Accuracy pondérée ($COEP$)** sur données d'enquête brutes scellées ($13\,045$ trajets) :
  $$\text{Accuracy} = \frac{\sum_{i=1}^N w_i \cdot \mathbb{I}(\hat{y}_i = y_i)}{\sum_{i=1}^N w_i}$$
* **Macro-F1 Score & LogLoss Multi-Classe** pour pénaliser les erreurs sur les classes minoritaires (Vélo à 4,1 %).

### 3.2 Échelle Macroscopique (Distributionnelle)
* **Erreur L1 / Total Variation Distance (TVD)** :
  $$\text{TVD}(P, Q) = \frac{1}{2} \sum_{m \in \text{Modes}} \left\vert P(m) - Q(m) \right\vert$$
* **Score Composite Multi-Strates ($\mathcal{L}_{\text{composite}}$)** :
  Pour s'assurer que le modèle ne compense pas des erreurs inverses entre sous-populations, la loss composite agrège la TVD globale et les TVD par strates démographiques :
  $$\mathcal{L}_{\text{composite}} = w_{\text{global}} \cdot \text{TVD}_{\text{global}} + \sum_{s \in \text{Strates}} w_s \cdot \text{TVD}_s \quad \text{avec} \quad \sum w = 1$$
  *Justification des poids :* $w_{\text{global}} = 0,40$, $w_{\text{âge}} = 0,20$, $w_{\text{motif}} = 0,20$, $w_{\text{distance}} = 0,20$, correspondant aux axes principaux de décomposition de la variance des choix de transport.

---

## 4. Protocole d'Ablation Incrémentale en 4 Paliers

L'évaluation compare systématiquement les modèles à travers 4 paliers d'information croissante :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PALIER 0 : PLANCHERS STATISTIQUES & HEURISTIQUES PHYSIQUES                  │
│ 0.1 Hasard Uniforme : Tirage aléatoire pur (25 % par mode) ──► 0 info.      │
│ 0.2 Prior Empirique (Zero-Rule) : Prédit toujours Voiture ──► 56,7 % acc.   │
│ 0.3 Heuristique du Plus Rapide : Min(Durée OTP) ──► Physique réseau pure.   │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 1 : MODÈLE NU / BARE LLM (Zero Prompt Engineering)                   │
│ • Profil complet personne + Itinéraires réels OpenTripPlanner (OTP).        │
│ • Prompt neutre : « Choisis l'itinéraire le plus approprié ».               │
│ • Modèles évalués :                                                         │
│   - Modèles Français / Européens : Mistral (Mistral-Small, Mistral-Nemo)    │
│   - Modèle Ouvert Local : Qwen-2.5-32B-Instruct (Déterministe tau=0.0)      │
│   - Modèle Propriétaire : Google Gemini-Flash                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 2 : MODÈLE CALIBRÉ (Prompt Engineering & Optimisation)               │
│ • Injection de consignes comportementales et personas enrichis.             │
│ • Mesure du gain net : Delta = Score(Calibré) - Score(Nu).                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 3 : BASELINES STATISTIQUES DE RÉFÉRENCE (Plafond Tabulaire)          │
│ • Modèle Économétrique de référence : Logit Multinomial (MNL de McFadden).  │
│ • Oracle Machine Learning Supervisé : LightGBM (78,5 % acc, LogLoss 0,54).  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Protocole d'Évaluation Écologique : Événements Réels Sourcés

Pour dépasser les contextes synthétiques arbitraires, les agents LLM sont évalués face à des **articles de presse locale et communiqués officiels réels et datés de la métropole toulousaine**.

### 5.1 Matrice des 4 Événements d'Actualité Sourcés

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. ÉVÉNEMENT CULTUREL / FESTIF (Attracteur piéton/TC & Blocage routier)     │
│ • Fait réel sourcé : Le passage du Minotaure dans les rues de Toulouse      │
│   (Compagnie La Machine - La Dépêche du Midi / Métropole).                  │
│ • Article brut injecté : « Hyper-centre piétonnisé, circulation fermée sur  │
│   les boulevards, métros renforcés, affluence piétonne exceptionnelle ».    │
│ • Hypothèse : Chute de l'usage voiture vers Métro et Marche.                │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. ÉVÉNEMENT ENVIRONNEMENTAL / RÉGULATOIRE (Incentive TC)                   │
│ • Fait réel sourcé : Pic de pollution à l'ozone et Alerte Canicule          │
│   (Arrêté préfectoral Haute-Garonne / Ticket Planète Tisséo à 3 €).         │
│ • Article brut injecté : « Transports collectifs à tarif réduit/gratuits,   │
│   circulation différenciée Crit'Air et recommandation d'éviter le vélo ».   │
│ • Hypothèse : Bascule vers TC climatisés et évitement du vélo à 14h.        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. INCIDENT D'INFRASTRUCTURE MAJEUR (Répulseur Voiture)                     │
│ • Fait réel sourcé : Accident grave et coupure du Périphérique Ouest        │
│   au niveau du pont d'Empalot (Flash Radio Vinci / La Dépêche).             │
│ • Article brut injecté : « Rocade coupée, +1h de bouchon estimé ».          │
│ • Hypothèse : Report modal d'urgence vers TER / Métro.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. PANNE MAJEURE RÉSEAU (Répulseur TC & Test Longitudinal d'Hystérésis)     │
│ • Fait réel sourcé : Panne informatique générale du Métro Ligne A Tisséo.   │
│ • Article brut injecté : « Métro à l'arrêt complet toute la soirée de 17h ».│
│ • Hypothèse : Bascule d'urgence à J, et persistance du churn à J+1..J+5.    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Protocole Expérimental Tripartite & Cinétique Temporelle
Pour chaque événement, trois conditions sont comparées sur une cohorte de $1\,000$ déplacements :
1. **Condition 1 (Base)** : LLM sans article de presse (régime nominal).
2. **Condition 2 (Info)** : LLM avec article de presse brut injecté dans le prompt.
3. **Condition 3 (Oracle)** : LightGBM supervisé (aveugle au texte d'actualité).

*Mesure :*
* Taux de bascule modal net : $\Delta \text{Mode} = \text{Choix}(\text{Info}) - \text{Choix}(\text{Base})$.
* Cinétique de dissipation de l'impact sur 5 jours consécutifs ($J+1$ à $J+5$) grâce au registre de mémoire $\mathcal{M}_t$.
