# Actions pour l'écriture du papier — AAMAS 2027

<!-- Dernière mise à jour : 2026-09-12 -->

Ce document centralise les **actions de rédaction**, les **points d'arbitrage méthodologique** et les **réponses préventives aux objections des relecteurs** pour les chapitres de l'article AAMAS 2027.

---

## 1. Risque pour la reproductibilité AAMAS (Données sous convention & Supplementary Material)

**Remarque / Objection de relecture :**
> *« Risque pour la reproductibilité AAMAS : Si un relecteur ne peut pas rejouer les expériences parce que les données d'enquête sont sous embargo/convention nominative, le code et la cohorte synthétique scellée doivent être intégralement décrits et rendus reproductibles dans le Supplementary Material (ZIP anonyme de 25 Mo). »*

**Diagnostic & Enjeux :**
- Les microdonnées brutes de l'enquête EMC² 2023 sont détenues sous la convention nominative `lil-1750` (Quetelet-Progedo-Diffusion), interdisant toute cession sous quelque forme que ce soit ([`sources/ENGAGEMENT_DONNEES_EMC2.md`](../sources/ENGAGEMENT_DONNEES_EMC2.md)).
- Un relecteur AAMAS ne pouvant pas ré-exécuter le pipeline sur les données sources peut contester la reproductibilité des résultats.

**Actions concrètes pour le papier :**
1. **Dans le texte de l'article (Chapitre 4 § 4.5 & § 4.7) :** Expliciter la frontière étanche entre :
   - les *microdonnées d'enquête réelles* (étalon statistique externe de référence et d'entraînement, non diffusables par engagement légal) ;
   - la *cohorte synthétique scellée v5* ($N = 1\,000$ personas, $3\,299$ déplacements cycliques, anonymisée, issue d'eqasim et de la sélection par ménages) : celle-ci est intégralement diffusable et auditable.
2. **Dans le Supplementary Material (ZIP anonyme de 25 Mo) :**
   - Intégrer le fichier `population.json` de la cohorte v5 avec son sceau d'intégrité sha256 (`de73532e…`).
   - Intégrer l'intégralité du code d'inférence, de calcul des métriques et des prompts (`mobility_core`, `mobility_llm`), les configurations d'expériences (`experiments.yaml`), les graines de tirage et le runner d'expériences sans simulateur (`services/llm-agents/experiences/runner.py`).
   - Fournir les scripts et instructions pour rejouer les prédictions et calculer les métriques d'évaluation en aveugle sur la cohorte synthétique.
3. **Documents liés :** [`SOUMISSION_AAMAS_2027.md`](SOUMISSION_AAMAS_2027.md) § 3, [`fr/04_metrics_and_substrate.md`](fr/04_metrics_and_substrate.md), [`fr/99_annexes.md`](fr/99_annexes.md) (Annexe G), [`ameliorations.md`](ameliorations.md) § 5.

---

## 2. Objection sur la portée de H0 : apport scientifique face au boosting tabulaire sur-spécialisé

**Remarque / Objection de relecture :**
> *« Prétendre que $H_0$ est une découverte majeure est exagéré : il est évident qu'un LLM nu ou légèrement prompté à la main ne peut pas battre un Gradient Boosted Tree (LightGBM) entraîné de façon supervisée sur 31 000 trajets locaux réels. Vous comparez un modèle non entraîné avec un modèle sur-spécialisé. Quel est l'apport scientifique réel au-delà de confirmer que le boosting tabulaire surpasse le zero-shot ? »*

**Diagnostic & Enjeux :**
- Si le papier laisse penser que le résultat principal est la « découverte » qu'un modèle zero-shot / few-shot perd face à un modèle supervisé sur 31 000 données d'entraînement, le jury rejettera l'article pour trivialité.

**Actions concrètes pour le papier :**
1. **Cadrage préventif dès l'introduction (§ 1.2 & § 1.3 C2) :**
   - Présenter $H_0$ non pas comme une surprise algorithmique, mais comme l'**établissement rigoureux d'une borne structurelle** (Tier 3 de SILICA) face au discours techno-optimiste de la littérature (CitySim, AgentMove) qui affirme ou suggère que les capacités de raisonnement des LLM suffisent à émuler fidèlement la mobilité humaine.
   - Poser l'**asymétrie d'exposition** (31 279 trajets réels vus contre 0) comme objet d'étude méthodologique : quel est le coût distributionnel de l'absence d'enquête locale pour une ville ?
2. **Démonstration de l'apport scientifique au-delà du régime nominal :**
   - **Régimes non tabulés (Section 7) :** L'oracle supervisé excelle sur la routine, mais s'avère **aveugle et amnésique** face aux chocs (panne inopinée, article de presse locale, alerte canicule). L'agent LLM y démontre sa véritable valeur ajoutée : adaptation sémantique et inertie cognitive (hystérésis sur 5 jours).
   - **L'architecture hybride en cascade (Section 8) :** L'apport n'est pas l'élimination du LLM, mais sa juste place : filtrage déterministe en amont, oracle tabulaire rapide et précis pour 90 % des flux nominaux (0 token, latence < 1 ms), et délégation au LLM pour les 10 % d'exceptions, d'incertitude ou de contextes complexes.
3. **Documents liés :** [`fr/01_introduction.md`](fr/01_introduction.md), [`fr/06_ablation.md`](fr/06_ablation.md) § 6.2/6.7, [`fr/08_limits_and_hybrid.md`](fr/08_limits_and_hybrid.md) § 8.1/8.2, [`ameliorations.md`](ameliorations.md) § 6.

---

## 3. Formalisation mathématique du dispositif agentique (Chapitre 3)

**Remarque / Action de rédaction :**
> *« Remplacer la description narrative du dispositif par une formalisation propre en un bloc compact :*
> $$\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$$
> *où :*
> - $P_i$ *est le persona socio-démographique scellé,*
> - $M_{i,t}$ *le registre de mémoire bi-composante (STM circulaire, LTM vectorielle),*
> - $C_i$ *l'état de la chaîne de véhicules du ménage, et*
> - $\pi_\theta(a \mid o_t, M_{i,t})$ *la distribution verbalisée sur l'espace d'action restreint $\mathcal{A}(o_t, C_i)$. »*

**Diagnostic & Enjeux :**
- Le chapitre 3 actuel ([`fr/03_architecture.md`](fr/03_architecture.md)) est rédigé sous une forme narrative (« retour au style narratif de la v0.1 »).
- Face aux exigences formelles d'AAMAS (critère *Dual Core* : formalisation formelle MAS rigoureuse couplée à l'empirisme), l'absence de formalisme mathématique expose l'article à l'objection d'un modèle d'agent purement discursif sans spécification d'état ni d'espace d'action.

**Actions concrètes pour le papier :**
1. **Remplacement en tête du chapitre 3 (§ 3.1 & § 3.3) :**
   - Remplacer les paragraphes narratifs par la définition formelle du tuple $\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$ dès la présentation du dispositif.
   - Poser l'espace des actions offertes $\mathcal{A}(o_t, C_i)$ conditionné par l'offre de transport instantanée $o_t$ (OTP/OSMnx) et le filtre d'éligibilité / localisation physique des véhicules $C_i$.
   - Définir rigoureusement la décision comme un tirage probabiliste $a_t \sim \pi_\theta(\cdot \mid o_t, M_{i,t})$ sur la distribution verbalisée, et non un argmax déterministe.
2. **Documents liés :** [`fr/03_architecture.md`](fr/03_architecture.md), [`ameliorations.md`](ameliorations.md) § 7, [`plan/PLAN.md`](plan/PLAN.md) § 3.

---

## 4. Synthèse des points de consolidation méthodologique

Le détail de chaque point technique et son protocole d'intégration sont suivis dans [`ameliorations.md`](ameliorations.md) :
1. **Effectif publié et témoin sans modèle** : Règle de comparabilité sur petites strates.
2. **Condition « temps terminal » (H1)** : Primauté de l'impédance physique du réseau sur les consignes de prompt.
3. **Condition few-shot ($k$ exemples)** : Séparer déficit informationnel et barrière cognitive structurelle.
4. **Version forte sur le prompt système** : Absence totale de formules de décision, seuils ou coefficients numériques.
5. **Risque de reproductibilité AAMAS** : Données sous convention nominative et cohorte scellée dans le ZIP.
6. **Objection sur la portée de $H_0$** : Apport scientifique réel et légitimité de l'architecture hybride en cascade.
7. **Formalisation mathématique du dispositif** : Tuple formel $\text{Agent}_i$ remplaçant la prose narrative en section 3.
