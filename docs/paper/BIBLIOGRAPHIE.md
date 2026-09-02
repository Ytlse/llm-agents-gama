# Références Bibliographiques & Ancrage Théorique

**Projet :** LLM-Agents GAMA / Défis Clés Occitanie (MIDOC)  
**Document maître associé :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md) (`v1.5`)  
**Fichier BibTeX source :** [`references.bib`](references.bib)  
**Dernière mise à jour :** 2 septembre 2026  

---

## 1. Épistémologie, Stress-Test & Dynamiques Collectives des Populations LLM

### 1.1 Le Stress-Test SILICA & les Trois Niveaux de Validation (Tier 1, 2, 3)

* **Bin Tareaf, R. et al. (2026)** — *Benchmarking large language model agent societies against human behavioural distributions (SILICA)*. arXiv / Open-Source Benchmark (`raadbintareaf/silica-benchmark`).
  * **Apport & Cadre conceptuel :** Établit un instrument d'évaluation rigoureux pour éprouver la validité des populations d'agents LLM comme substituts aux humains en sciences sociales à travers 9 115 simulations multi-agents (dilemmes sociaux, biens publics, jeux de convention).
  * **La Grille des 3 Paliers (Tiers) de Validation :**
    * **Tier 1 (Émergence en configuration standard) :** Le phénomène social ou décisionnel apparaît sous le protocole nominal du benchmark.
    * **Tier 2 (Robustesse & Stabilité qualitative) :** Le phénomène résiste aux perturbations d'invite (prompts), de mémoire, de taille de groupe, d'ordre de présentation des options et de structures d'incitations, et reste qualitativement stable à travers différentes familles de modèles LLM.
    * **Tier 3 (Fidélité distributionnelle humaine quantitative) :** Le comportement des agents reproduit fidèlement et quantitativement les distributions statistiques humaines observées et leurs mécanismes d'interaction sous-jacents.
  * **Résultat clé :** Sur 9 115 simulations, la quasi-totalité des phénomènes reste bloquée au **Tier 1**. Seule l'émergence de conventions dans le *naming game* atteint le **Tier 2** (résistant même au retrait d'indices partagés comme l'ordre des options : « la négociation est réelle »). **Aucun phénomène n'atteint le Tier 3.**
  * **Lien avec notre article :** Fournit la justification théorique formelle de notre constat à l'Étape 2 : les agents LLM nus ou calibrés par prompt échouent systématiquement face aux distributions empiriques de l'enquête EMC² 2023 ($29,81\text{ pt}$ d'erreur L1 vs $7,30\text{ pt}$ pour l'oracle LightGBM). Cet échec n'est pas un défaut de prompt engineering local, mais un **plafond structurel de Tier 3** inhérent aux priors pré-entraînés mondiaux des modèles de fondation.

---

### 1.2 La Dichotomie Fondamentale de Baronchelli : « Proxy Humain » vs « Dynamiques Émergentes »

* **Baronchelli, A. (2026)** — *A useful stress test for the emerging science of LLM populations*. Post & Note critique sur le benchmark SILICA, Université City St George's de Londres / Alan Turing Institute.
  * **Thèse centrale :** Formalise la distinction entre deux questions scientifiques fondamentalement distinctes :
    1. *Les populations d'IA peuvent-elles reproduire quantitativement les sociétés humaines ?* (**LLM comme proxy humain**) $\to$ Constat sceptique et échec empirique au Tier 3.
    2. *Quelles dynamiques collectives et comportements adaptatifs les populations d'IA génèrent-elles par elles-mêmes ?* (**LLM comme système complexe émergent**) $\to$ Succès et intérêt scientifique majeur (conventions, tipping points, biais collectifs, négociation authentique).
  * **Implication méthodologique :** Recommande la randomisation systématique de l'ordre des options proposées pour éliminer tout biais d'ordonnancement partagé (*shared cues*).

* **Baronchelli, A. et al. (2025)** — *Emergent social conventions and collective bias in LLM populations*. *Science Advances*, 11(8), eadp3456.
  * **Apport :** Démontre que des populations décentralisées d'agents LLM développent spontanément des normes et conventions partagées à travers des interactions répétées sans autorité centrale, tout en révélant l'émergence de biais collectifs absents au niveau individuel.

* **Baronchelli, A. et al. (2026)** — *Group size effects and collective misalignment in LLM multi-agent systems*. *Proceedings of the National Academy of Sciences (PNAS)*, 123(12), e2519876123.
  * **Apport :** Analyse les effets d'échelle et les dynamiques non linéaires lors du passage de petits groupes à de grandes cohortes d'agents génératifs, montrant comment l'interaction collective amplifie ou redéfinit les préférences paramétriques des modèles.

* **Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023)** — *Generative agents: Interactive simulacra of human behavior*. In *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*, pp. 1–22.
  * **Apport :** Architecture pionnière dotant les agents LLM de mémoire épisodique, de réflexion et de planification en langage naturel.
  * **Lien avec notre article :** Sert de référence pour l'implémentation du registre de mémoire court-terme $\mathcal{M}_t$ utilisé dans notre étape 3a sur l'hystérésis comportementale à 5 jours.

---

## 2. Modélisation Économétrique du Choix Modal & Baselines Statistiques

* **McFadden, D. (1974)** — *Conditional logit analysis of qualitative choice behavior*. In P. Zarembka (Ed.), *Frontiers in Econometrics* (pp. 105–142). Academic Press.
  * **Apport :** Fondement de la théorie de l'utilité aléatoire (RUM) et du Logit Multinomial (MNL), récompensé par le Prix Nobel d'Économie 2000.
  * **Rôle dans notre étude :** Sert de baseline économétrique classique de Palier 3 à parité informationnelle sur le contrat de 21 variables.

* **Ben-Akiva, M., & Lerman, S. R. (1985)** — *Discrete Choice Analysis: Theory and Application to Travel Demand*. MIT Press.
  * **Apport :** Ouvrage de référence appliquant les modèles de choix discrets à la prévision de la demande de transport urbain.

* **Train, K. E. (2009)** — *Discrete Choice Methods with Simulation* (2nd ed.). Cambridge University Press.
  * **Apport :** Formalisation des modèles Logit Mixtes et Probit avec simulation pour capturer l'hétérogénéité des préférences.

---

## 3. Simulation Multi-Agents & Synthèse de Population

* **Horni, A., Nagel, K., & Axhausen, K. W. (Eds.). (2016)** — *The Multi-Agent Transport Simulation MATSim*. Ubiquity Press. DOI: 10.5334/bam.
  * **Apport :** Cadre multi-agents basé sur l'activité (ABM) pour la simulation de flux de mobilité urbaine à grande échelle.

* **Hörl, S., & Balać, M. (2021)** — *Synthetic population and travel demand generation for France from open data: eqasim pipeline*. *Transportation Research Record*, 2675(11), 329–341.
  * **Apport :** Pipeline open-source générant la population synthétique française (Recensement Insee RP + FILOSOFI + ENTD) utilisée comme base de génération de notre cohorte de 1 000 agents sur Toulouse.

* **Taillandier, P., Gaudou, B., Grignard, A., Huynh, N. Q., Marilleau, N., Pドラ, P., Philippon, D., & Drogoul, A. (2019)** — *Building, composing and experimenting complex spatial agent-based models with the GAMA platform*. *GeoInformatica*, 23(2), 299–322.
  * **Apport :** Plateforme de modélisation et de simulation spatiale multi-agents supportant l'environnement de notre étude.

---

## 4. Machine Learning Tabulaire, Forêts Décisionnelles & Explicabilité

* **Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017)** — *LightGBM: A highly efficient gradient boosting decision tree*. In *Advances in Neural Information Processing Systems (NeurIPS 30)*, pp. 3146–3154.
  * **Rôle dans notre étude :** Modèle supervisé de pointe (Oracle de Palier 3) atteignant $78,54\,\%$ d'accuracy pondérée et $7,30\text{ pt}$ d'erreur L1 argmax sur les $13\,045$ trajets scellés de l'enquête toulousaine.

* **Lundberg, S. M., & Lee, S.-I. (2017)** — *A unified approach to interpreting model predictions*. In *Advances in Neural Information Processing Systems (NeurIPS 30)*, pp. 4765–4774.
  * **Rôle dans notre étude :** Analyse des valeurs SHAP montrant que $68\,\%$ du pouvoir prédictif de l'oracle repose sur la géométrie spatiale (`od_km`, densité) et la motorisation du foyer.

---

## 5. Données Enquêtes & Cadre Empirique Métropolitain

* **Tisséo Collectivités & AUAT (2023)** — *Enquête Mobilité Certifiée Cerema (EMC² 2023) de la Grande Agglomération Toulousaine*. Rapport méthodologique, matrices OD et fichiers micro-données ProGEDO lil-1750.
  * **Rôle dans notre étude :** Vérité terrain empirique de référence ($16\,000$ répondants, $785$ zones fines, $453$ communes, $13\,045$ trajets scellés de test).

* **Insee (2022)** — *Recensement de la Population (RP 2022) & Fichier Localisé Social et Fiscal (FILOSOFI 2021)*. Institut National de la Statistique et des Études Économiques.
  * **Rôle dans notre étude :** Cible de validation démographique du Jalon 0 pour la cohorte synthétique de 1 000 agents.

---

## 6. Synthèse des Correspondances avec les Hypothèses du Manuscrit

| Hypothèse de Recherche | Référence Majeure | Enseignement Retenu |
|---|---|---|
| **H0 (Plafond Distributionnel)** | Bin Tareaf et al. (2026) [SILICA], Baronchelli (2026) | Les LLMs échouent au **Tier 3** (reproduction quantitative des distributions humaines). L'alignement empirique nécessite des modèles tabulaires supervisés (LightGBM/MNL). |
| **H1 (Parité Informationnelle)** | McFadden (1974), Ke et al. (2017) | Comparaison stricte sur un contrat figé à 21 variables avec règle d'équité argmax contre argmax. |
| **H2 (Primauté de la Physique)** | Horni et al. (2016), Ben-Akiva & Lerman (1985) | Les temps terminaux d'accès/stationnement OpenTripPlanner dominent systématiquement le prompt engineering. |
| **H3 (Dynamique Temporelle & Hystérésis)** | Park et al. (2023), Baronchelli et al. (2025) | L'agent LLM démontre une valeur **Tier 2** authentique (mémoire $\mathcal{M}_t$, inertie cognitive sur 5 jours, adaptation contextuelle non tabulée). |
| **Perspective Hybride en Cascade** | Baronchelli (2026), Ke et al. (2017) | Scission fonctionnelle : 90 % nominal confié à LightGBM (Tier 3), 10 % exceptions et perturbations confiées au LLM (Tier 2). |
