---
name: optimiser-prompt-experience
description: >-
  Analyser les dérives modales d'une expérience de mobilité (scores, strates, personas),
  diagnostiquer les sophismes du LLM, concevoir des mutations cognitives sans seuil explicite
  ni formule mathématique, rejouer 20 cas par mutation via Antigravity et proposer un prompt candidat.
---

# Optimiser le Prompt Système d'une Expérience

Ce skill formalise la méthodologie complète pour améliorer le prompt système d'une expérience de mobilité à partir de l'analyse détaillée de ses résultats, sans biais prescriptif (interdiction formelle des seuils kilométriques ou formules mathématiques).

---

## 1. Paramètres d'Entrée

La commande cible une expérience précise :
- **Nom de l'expérience** : `<NOM_EXP>` (ex: `exp_gemini-35-fl_expcham6_jtir_t0_nosim`)
- **Horodatage d'exécution** (optionnel) : `<TIMESTAMP>` (si omis, prendre la dernière exécution terminée dans `data/experiences/<NOM_EXP>/executions/`).

---

## 2. Phase 1 — Diagnostic Analytique Détail par Détail

### 2.1 Évaluation Globale et Écarts de Référence
Inspecter `scores.json`, `synthese.json` et `moves.csv` dans le dossier d'exécution :
1. Calculer l'écart global des parts modales (actual vs target de l'enquête ménages déplacements / Cerema).
2. Relever les scores composites : distance L1 et divergence EMD-JSD.

### 2.2 Analyse Détaillée par Strate
Extraire les écarts L1 et dérives (actual − target) pour chacune des 7 dimensions de `scores.json` :
- `age` : tranches de 5-9 ans à 75+ ans.
- `distance` : 0-1km, 1-2km, 2-5km, 5-10km, 10-20km, 20-50km.
- `lieu_residence` : Toulouse (centre dense), 1ère couronne, 2ème couronne, 3ème couronne.
- `type_logement` : habitat collectif (grand/petit), individuel (isolé/accolé).
- `occupation` : retraités, étudiants, actifs plein temps, temps partiel, chômeurs, foyers, scolaires.
- `motif` : travail, études, achats, loisirs, etc.
- `genre` : homme, femme.

Classer les strates par erreur L1 décroissante pour isoler les foyers de dérive prioritaires.

### 2.3 Identification des $N$ Archétypes de Personas Dérivants
Regrouper les strates défaillantes en archétypes comportementaux majeurs (typiquement 4 à 6 archétypes), par exemple :
- **Aînés / Retraités (65+ ans)** : sur-report massif de la marche de proximité vers les transports collectifs.
- **Citadins en habitat collectif dense** : abandon de la marche directe au profit de bus/métros pour des sauts de puce.
- **Actifs navetteurs en heure de pointe** : sous-utilisation de la voiture face à des transports collectifs à correspondances multiples.
- **Déplacements pour achats / courses** : surpondération du transport collectif ignorant la contrainte d'emport de charge.
- **Trajets de proximité (1-2 km)** : surestimation du gain de temps théorique d'un véhicule motorisé.

### 2.4 Diagnostic Qualitatif des Justifications (`decisions.jsonl`)
Inspecter les champs `raison` et `reponse_brute` dans `decisions.jsonl` pour déceler les **sophismes cognitifs** projetés par le LLM :
- *Sophisme des coûts irrécupérables* : « étant abonné, il préfère rentabiliser son abonnement » (oubli que la marche est 100% gratuite et immédiate).
- *Biais d'assistance / paternalisme senior* : « 78 ans, la marche fatigue » (oubli de la pénibilité bien plus forte du bus : montées de marches, freinages, attente debout sans banc).
- *Illusion du gain théorique* : préférer un bus de 14 minutes avec 11 minutes de marche d'approche plutôt qu'une marche directe de 18 minutes.
- *Négligence de la charge matérielle* : envoyer un acheteur en transport en commun avec des sacs lourds.

---

## 3. Phase 2 — Règles d'Or de Conception des Mutations Cognitives

> [!CAUTION]
> **Interdiction absolue des consignes explicites de mode et de formules mathématiques** :
> - Interdit d'écrire : « Si la distance est inférieure à 2 km, choisis la marche » ou « Au-dessus de 5 km, privilégie la voiture ».
> - Interdit d'introduire des fonctions d'utilité mathématiques ($U = \beta \cdot T + \dots$).
>
> Une consigne prescriptive transforme le modèle en thermostat artificiel et détruit la validité de l'expérience.

### Principes de Rédaction Valides
Chaque mutation doit agir sur le **cadre d'évaluation cognitive et d'empathie situationnelle** :
1. **Friction de chaîne et proportionnalité de l'effort** : comparer la part piétonne contenue dans l'option collective à la marche directe.
2. **Logistique d'emport et charge utile** : intégrer la réalité physique des sacs, bagages et encombrements.
3. **Autonomie et motricité apaisée des aînés** : valoriser la marche libre à son rythme face au stress des bousculades et chutes en transport en commun.
4. **Coût marginal réel et neutralité de l'équipement** : rappeler qu'un abonnement est un coût fixe déjà payé et qu'on n'« amortit » rien sur un saut de puce où la marche est gratuite.
5. **Valeur du temps de vie pour les actifs** : peser le coût d'un trajet qui double ou triple sur le repos et la vie personnelle.

---

## 4. Phase 3 — Protocole de Rejeu Empirique (20 Cas par Mutation)

Pour valider que chaque mutation va dans le bon sens avant de l'adopter :

### 4.1 Échantillonnage Stratifié
Extraire de `decisions.jsonl` **20 cas représentatifs distincts** (`person_id` uniques) pour chaque mutation :
- 20 cas de seniors sur sorties courtes.
- 20 cas de motifs achats avec transport collectif surestimé.
- 20 cas de proximité 1-2 km.
- 20 cas d'actifs en trajet travail avec fort différentiel voiture/TC.
- 20 cas d'abonnés choisissant le TC sur courte distance.

### 4.2 Exécution des Cas Tests
1. Rendre les prompts exacts (system prompt avec la mutation + user prompt des personas) via `PromptManager`.
2. Découper en lots équilibrés (5 à 10 personas par lot pour préserver l'intégrité JSON).
3. Soumettre les lots à l'évaluation (via sous-agents Antigravity ou runner IPC).
4. Récupérer les distributions de probabilités prédites.

### 4.3 Critère de Rétention
Comparer la part modale moyenne avant (baseline) et après mutation :
- La mutation est **conservée** si le mode hyper-représenté régresse au profit des modes réels lésés (ex: baisse du TC, hausse de la marche ou de la voiture selon la strate).
- La mutation est **rejetée ou reformulée** si elle produit un effet pervers ou reste inefficace.

---

## 5. Phase 4 — Proposition du Prompt Candidat et Clôture

1. Combiner l'ensemble des 5 mutations retenues dans une variante unifiée (ex: `expert_chaine_m7`).
2. Mettre à jour `mobility_llm/src/mobility_llm/prompts/prompts.yaml` avec :
   - Le texte intégral de la variante.
   - Le bloc `_provenance` détaillant la dérivation, les mutations et les mesures empiriques.
3. Rédiger le rapport de restitution présentant :
   - Les résultats détail par détail de l'expérience source.
   - Les personas dérivants et leurs métriques.
   - Les 5 mutations testées et leurs deltas sur les 20 cas.
   - Le prompt final recommandé pour la non-régression globale.
