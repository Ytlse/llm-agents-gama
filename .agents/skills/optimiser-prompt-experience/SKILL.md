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

### 2.3 Diagnostic des Mécanismes Comportementaux Sous-Jacents
Si l'analyse statistique s'appuie sur les strates de l'enquête pour localiser les dérives, **la conception des mutations ne doit jamais calquer ces strates**. L'objectif est d'identifier le *concept situationnel* ou la *friction réelle* que le LLM interprète de travers :
- Dérive sur les trajets d'achats → *Concept : logistique d'emport (courses légères d'appoint vs volume de coffre)*.
- Dérive sur les 1-2 km → *Concept : frictions fixes d'accès au véhicule motorisé (stationnement, manœuvre) vs prévisibilité de la marche*.
- Dérive sur les étudiants ou demandeurs d'emploi → *Concept : arbitrage budgétaire et poids du coût récurrent de l'automobile face aux modes gratuits ou accessibles*.
- Dérive sur les aînés → *Concept : préservation de l'autonomie motrice, fatigue continue vs stress et ruptures de charge des transports collectifs*.
- Dérive par temps froid ou pluvieux → *Concept : évaluation de l'exposition réelle aux intempéries (gêne ordinaire vs intempérie bloquante)*.

### 2.4 Diagnostic Qualitatif des Justifications (`decisions.jsonl`)
Inspecter les champs `raison` et `reponse_brute` dans `decisions.jsonl` pour déceler les **sophismes cognitifs** projetés par le LLM :
- *Sophisme du coffre systématique* : attribuer 80% de voiture pour une course de 800 m sous prétexte d'emport.
- *Météo-paranoïa* : basculer à 90% voiture dès qu'une pluie fine ou une température ordinaire de 8°C est mentionnée.
- *Projection universelle du cadre pressé* : supposer que tout déplacement répond à un impératif d'urgence ignorant les coûts financiers.
- *Biais disqualifiant induit par la consigne de sortie* : inciter le modèle à construire un argument contre la marche (ex. « pourquoi la marche n'obtient pas la plus forte probabilité »).

---

## 3. Phase 2 — Règles d'Or de Conception des Mutations Cognitives

> [!CAUTION]
> **Règle 1 — Neutralité catégorielle absolue : interdiction d'encoder les catégories de l'enquête** :
> - **Ne JAMAIS nommer ni cibler directement les catégories sociodémographiques de l'enquête (Cerema/EDGT)** :
>   * Pas de classes d'âge nommées (« jeunes », « aînés », « personnes âgées », « scolaires », « seniors », « enfants »).
>   * Pas de statuts socioprofessionnels (« étudiants », « actifs », « retraités », « chômeurs », « cadres »).
>   * Pas de types d'habitat ni zonages géographiques (« habitat collectif », « maison individuelle », « couronne », « banlieue »).
> - **Raisonner exclusivement en concepts universels, valeurs d'arbitrage et contraintes situationnelles réelles** :
>   * Au lieu de cibler les actifs → Parler de *gestion de l'emploi du temps contraint* et d'*engagements horaires stricts*.
>   * Au lieu de cibler les jeunes ou étudiants → Parler d'*arbitrage budgétaire*, de *niveau de ressources* et de *coût récurrent d'un véhicule motorisé face aux modes gratuits ou collectifs accessibles*.
>   * Au lieu de cibler les personnes âgées → Parler de *préservation de l'autonomie motrice*, de *sensibilité à la fatigue physique*, aux secousses et aux ruptures de charge.
>   * Au lieu de cibler un zonage → Parler d'*accès immédiat de quartier*, de *frictions fixes de stationnement* ou de *liaisons périphériques lointaines*.

> [!CAUTION]
> **Règle 2 — Interdiction des consignes prescriptives de mode, des seuils et des formules** :
> - Interdiction formelle de seuils kilométriques ou temporels (ex: « sous 2 km », « au-delà de 30 min »).
> - Interdiction formelle de consignes directes de mode (ex: « privilégier la marche », « choisir le bus »).
> - Interdiction formelle de formules d'utilité mathématiques ($U = \beta \cdot T + \dots$).
> - **Neutralité stricte de l'instruction de justification** : consigne neutre `Justifie la répartition en une phrase concise.`, sans clause incitant à disqualifier un mode précis (règle M1).

### Principes Conceptuels Valides
Chaque mutation doit agir sur l'**empathie situationnelle et le discernement qualitatif** :
1. **Friction de chaîne et proportionnalité de l'effort** : comparer la part d'approche/attente/diffusion au trajet global continu.
2. **Logistique d'emport et courses du quotidien** : distinguer les achats volumineux justifiant un coffre des courses légères et fréquentes de quartier.
3. **Autonomie motrice et préservation physique** : valoriser la marche continue et paisible à son propre rythme face à la pénibilité et aux secousses des transports collectifs.
4. **Réalité budgétaire et coût d'usage** : intégrer le niveau de ressources et le poids récurrent d'un véhicule individuel face à la gratuité des modes actifs et aux réseaux collectifs accessibles.
5. **Frictions fixes de l'automobile** : rappeler que sur courte liaison, le gain théorique au volant est souvent absorbé par les manœuvres, l'accès au véhicule et la recherche de stationnement.
6. **Gestion de l'emploi du temps contraint** : arbitrer sur la valeur du temps personnel lorsque les correspondances allongent excessivement la journée.
7. **Exposition réelle aux intempéries** : proportionner la gêne météo à l'exposition effective (temps ordinaire vs intempéries sévères).

---

## 4. Phase 3 — Protocole de Rejeu Empirique (20 Cas par Mutation)

Pour valider l'impact réel de chaque mutation avant son adoption :

### 4.1 Échantillonnage Stratifié
Extraire de `decisions.jsonl` **20 cas représentatifs distincts** (`person_id` uniques) pour chaque dimension conceptuelle :
- 20 cas de liaisons courtes avec vulnérabilité physique ou fatigue.
- 20 cas d'achats du quotidien avec transport collectif ou voiture disproportionnés.
- 20 cas de proximité 1-2 km avec surestimation de la vitesse automobile.
- 20 cas d'arbitrage budgétaire (ressources limitées, coût de l'automobile).
- 20 cas sous météo fraîche ou pluvieuse ordinaire.

### 4.2 Exécution des Cas Tests
1. Rendre les prompts exacts (system prompt avec la mutation candidate + user prompt des personas) via `PromptManager`.
2. Découper en lots équilibrés (5 à 10 personas par lot pour préserver l'intégrité JSON).
3. Soumettre les lots à l'évaluation (via sous-agents Antigravity).
4. Récupérer les distributions de probabilités prédites.

### 4.3 Critère de Rétention
Comparer la part modale moyenne avant (baseline) et après mutation :
- La mutation est **retenue** si le mode hyper-représenté reflue vers des parts réalistes au profit des modes rationnellement légitimes.
- La mutation est **rejetée ou reformulée** si elle induit un contre-biais ou dégrade d'autres modes.

---

## 5. Phase 4 — Proposition du Prompt Candidat et Clôture

1. Combiner l'ensemble des mutations conceptuelles validées dans une variante unifiée (ex: `expert_gem_3.8_v3`).
2. Mettre à jour `packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml` avec :
   - Le texte intégral de la variante.
   - Le bloc `_neutralite` conforme (verdict, date, règles évaluées, sha256_texte officiel).
   - Le bloc `_provenance` détaillant la dérivation, les mutations conceptuelles et les mesures empiriques.
3. Vérifier la validité avec `PromptManager` et exécuter la suite de tests unitaires.
4. Rédiger le rapport de restitution présentant le diagnostic, les mutations, les métriques comparatives et les perspectives de validation globale sur la cohorte scellée.
