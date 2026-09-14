# Ticket 072 — Impact de la langue à l'inférence, conversations d'agents en français et cadrage contextuel et culturel explicite (AAMAS)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.  
> Ouvert le 2026-09-14.  
>  
> **Catégorie** : Expériences & Cognition (🧠) / Rédaction & Publication (📝)  
> **Statut initial** : `à faire`  
>  
> **Touche potentiellement** : Chapitre 4 (§ 4.3 substrat et contrat d'information), Chapitre 5 (§ 5.1 prompt factuel neutre, § 5.2 benchmark multi-modèles, § 5.3 variabilité), Chapitre 7 (scénarios exogènes), et Annexes méthodologiques (Rebuttal defence AAMAS 2027).

---

## 1. Contexte & Problématique Scientifique (AAMAS)

Dans les simulations multi-agents (ABM) de mobilité urbaine fondées sur des modèles de fondation (LLM), l'intégralité de nos prompts de décision modale et des interactions entre agents (notamment la négociation intra-ménage pour le partage de la voiture du foyer, cf. [ticket 018](ticket_018_partage_voiture_foyer.md)) est actuellement formulée en **français**.

Cette situation soulève une double interrogation critique pour la publication internationale à **AAMAS 2027** :

1. **L'illusion de la neutralité linguistique** : Les modèles de fondation génériques (familles Gemini, GPT, Claude, Llama, Qwen, Mistral) sont pré-entraînés et alignés (RLHF) très majoritairement sur des corpus anglophones (> 80 à 90 %). Même pour des modèles performants en français, leur **espace latent par défaut** porte des représentations culturelles, des associations statistiques et des stéréotypes profondément anglo-saxons (ex. sur-valorisation de l'automobile individuelle, perception négative des transports collectifs, sous-estimation de la marchabilité des centres urbains denses européens).
2. **Le risque de la variable confondante (*Confounding Factor*) au Rebuttal AAMAS** : Un relecteur rigoureux ou hostile attaquera immédiatement le protocole :
   > *« Is the observed modal split drift (transit over-attraction, walk under-estimation) an authentic cognitive choice of the synthetic agents, or merely an artifact of multilingual prompt tokenization, syntactic overhead, and non-English alignment degradation? »*
3. **Le coût et la dynamique conversationnelle multi-agents** : Lorsque les agents conversent en langage naturel libre en français pour arbitrer des ressources rivales (véhicule partagé du ménage), deux écueils apparaissent :
   - Un biais de complaisance (*sycophancy*) et de politesse non réaliste qui altère l'équilibre de jeu théorique.
   - Une explosion du coût de tokenisation (+20 % à +40 % en français du fait des découpages BPE/SentencePiece sur les caractères accentués et flexions).

---

## 2. Règle Cardinale & Recommandations Méthodologiques

> ### 📌 Principe Fondateur : Combinaison de la Langue et du Contexte
> **Le passage au français seul ne suffit pas à obtenir une simulation authentique.**  
> Il est impératif de **forcer explicitement le cadrage culturel et territorial dans le prompt** (références socio-économiques locales, nomenclatures INSEE, habitudes de vie urbaines et métropolitaines françaises, aménagement cyclable et réseau Tisséo) pour éloigner activement le modèle de son espace latent par défaut et ancrer la décision dans l'écologie réelle du territoire de Toulouse.

Trois niveaux de cadrage doivent être formalisés :
- **Niveau Linguistique** : Définir si la langue d'inférence est le français natif ou l'anglais, et mesurer le différentiel de performance/fidélité.
- **Niveau Culturel & Territorial** : Injecter les contraintes sociodémographiques réelles (catégories socioprofessionnelles, composition du ménage, chaîne d'activités quotidienne) sans heuristique d'arbitrage biaisée.
- **Niveau Protocolaire Multi-Agent** : Encadrer les dialogues inter-agents dans des protocoles bornés (interaction en 2 tours, extraction JSON structurée) pour éviter la divergence conversationnelle.

---

## 3. Corpus Bibliographique & Documents Clés à Analyser

Un travail approfondi de recensement de la littérature scientifique sur l'impact de la langue, de l'inférence multilingue et du cadrage culturel a été constitué via Elicit :  
🔗 **Artifact de référence** : [Elicit Artifact 9e07f2d9-9433-4ef7-96b6-b00792580f81](https://elicit.com/artifact/9e07f2d9-9433-4ef7-96b6-b00792580f81)

L'ensemble des documents, métadonnées associées et articles ont été centralisés dans le dossier :  
📂 **[`docs/paper/mémoire/`](../paper/mémoire/)** (index maître et fichiers associés).

> ⚠️ **Directive de travail** :  
> **Il est indispensable d'analyser l'ensemble des documents ci-dessous (ainsi que les tickets de modélisation du dépôt liés à la cognition et aux interactions) pour asseoir scientifiquement notre démarche et blinder notre soumission AAMAS.**

### Tableau de Synthèse des 30 Travaux du Corpus

| N° | Titre du Document | Focus Analytique | Pertinence pour notre Papier | Source / DOI / Lien |
| :---: | :--- | :--- | :--- | :--- |
| **01** | **FIBER: A Multilingual Evaluation Resource for Factual Inference Bias** | Biais factuel induit par la langue du prompt | **Directe** | [ACL Anthology](https://aclanthology.org/2024.lrec-main.95.pdf) |
| **02** | **Whose morality do they speak? Unraveling cultural bias in multilingual language models** | Biais culturel et moral multilingue | **Directe** | [10.1016/j.nlp.2025.100172](https://doi.org/10.1016/j.nlp.2025.100172) |
| **03** | **Whose Morality Do They Speak? Unraveling Cultural Bias in Multilingual Language Models** | Biais culturel et moral multilingue (corpus étendu) | **Directe** | [arXiv:2311.09633](https://arxiv.org/abs/2311.09633) |
| **04** | **7 Points to Tsinghua but 10 Points to ? Assessing Large Language Models in Agentic Multilingual National Bias** | Recommandations, agents autonomes et biais national selon la langue | **Très directe (simulation sociale)** | [ACL Findings](https://aclanthology.org/2024.findings-acl.844.pdf) |
| **05** | **Language Matters: How Do Multilingual Input and Reasoning Paths Affect Large Reasoning Models?** | Impact de la langue sur les chemins de raisonnement (CoT) et la logique | **Directe** | [Semantic Scholar](https://www.semanticscholar.org/paper/c692f46475f194662ab9fec8e984fb005284553f) |
| **06** | **Cross-Language Bias Examination in Large Language Models** | Analyse comparée des biais cognitifs entre langues | **Directe** | [arXiv](https://arxiv.org) |
| **07** | **Ethical Reasoning and Moral Value Alignment of LLMs Depend on the Language We Prompt Them in** | Dépendance de l'alignement et des arbitrages de valeurs à la langue du prompt | **Directe** | [arXiv:2404.18460](https://arxiv.org/abs/2404.18460) |
| **08** | **Prompting language influences diagnostic reasoning and accuracy of large language models** | Impact de la langue sur la rigueur du raisonnement diagnostic et l'exactitude | **Directe (domaine décisionnel)** | [Semantic Scholar](https://www.semanticscholar.org/paper/580c557701d468ef04481b94398c7f14facbb595) |
| **09** | **LLMs and Cultural Values: the Impact of Prompt Language and Explicit Cultural Framing** | Effet combiné de la langue du prompt et du cadrage culturel explicite | **Centrale / Pivot de notre thèse** | [arXiv:2403.11180](https://arxiv.org/abs/2403.11180) |
| **10** | **x1: Learning to Think Adaptively Across Languages and Cultures** | Adaptation dynamique du raisonnement aux spécificités culturelles | **Directe** | [arXiv:2604.16917](https://doi.org/10.48550/arXiv.2604.16917) |
| **11** | **Cross-Lingual Consensus: Aligning Multilingual Cultural Knowledge via Multilingual Self-Consistency** | Cohérence culturelle interlangue et consensus d'échantillonnage | **Directe** | [arXiv](https://arxiv.org) |
| **12** | **MCEval: A Dynamic Framework for Fair Multilingual Cultural Evaluation of LLMs** | Cadre d'évaluation dynamique et équitable des biais culturels multilingues | **Directe** | [arXiv](https://arxiv.org) |
| **13** | **CulFiT: A Fine-grained Cultural-aware LLM Training Paradigm via Multilingual Critique Data Synthesis** | Synthèse de critiques pour sensibiliser le modèle à la culture locale | **Pertinente** | [arXiv](https://arxiv.org) |
| **14** | **Disentangling Language and Culture for Evaluating Multilingual Large Language Models** | Découplage formel entre signal linguistique et composante culturelle | **Très directe** | [arXiv:2405.00656](https://arxiv.org/abs/2405.00656) |
| **15** | **Having Beer after Prayer? Measuring Cultural Bias in Large Language Models** | Mesure de cohérence contextuelle et de non-sens culturel dans les LLMs | **Directe** | [arXiv](https://arxiv.org) |
| **16** | **Is Translation All You Need? A Study on Solving Multilingual Tasks with Large Language Models** | Traduction vers l'anglais pivot versus inférence directe en langue native | **Très directe (arbitrage méthodologique)** | [arXiv:2403.10258](https://arxiv.org/abs/2403.10258) |
| **17** | **A Dual-Layered Evaluation of Geopolitical and Cultural Bias in LLMs** | Évaluation à double niveau des biais géopolitiques et culturels | **Directe** | [arXiv](https://arxiv.org) |
| **18** | **Decoding Multilingual Moral Preferences: Unveiling LLM's Biases Through the Moral Machine Experiment** | Préférences morales multilingues appliquées à la mobilité et aux dilemmes | **Directe** | [arXiv](https://arxiv.org) |
| **19** | **See It from My Perspective: Diagnosing the Western Cultural Bias of Large Vision-Language Models in Image Understanding** | Diagnostic du biais culturel occidental dans les modèles de fondation | **Adjacente** | [arXiv](https://arxiv.org) |
| **20** | **Mitigating Cross-Lingual Cultural Inconsistencies in LLMs via Consensus-Driven Preference Optimisation** | Réduction des incohérences interlangues par optimisation de préférences | **Pertinente** | [arXiv](https://arxiv.org) |
| **21** | **Language-Specific Latent Process Hinders Cross-Lingual Performance** | Processus latents propres à chaque langue freinant le transfert | **Très directe (espace latent)** | [arXiv:2405.08803](https://arxiv.org/abs/2405.08803) |
| **22** | **When Models Reason in Your Language: Controlling Thinking Language Comes at the Cost of Accuracy** | Dégradation de l'exactitude lors du forçage de la langue de pensée CoT | **Très directe (choix CoT)** | [EMNLP Findings](https://aclanthology.org/2024.findings-emnlp.664.pdf) |
| **23** | **Exploring Multi-Lingual Bias of Large Code Models in Code Generation** | Biais multilingue dans les représentations logiques et de code | **Adjacente** | [arXiv](https://arxiv.org) |
| **24** | **When Models Reason in Your Language: Controlling Thinking Trace Language Comes at the Cost of Accuracy** | Compromis précision / langue imposée sur les traces de raisonnement | **Très directe** | [arXiv](https://arxiv.org) |
| **25** | **When Tom Eats Kimchi: Evaluating Cultural Bias of Multimodal Large Language Models in Cultural Mixture Contexts** | Biais culturel en contexte de mélange culturel | **Adjacente** | [arXiv](https://arxiv.org) |
| **26** | **When Language Shapes Thought: Cross-Lingual Transfer of Factual Knowledge in Question Answering** | Influence de la langue sur la structuration des faits et de la logique | **Directe** | [arXiv](https://arxiv.org) |
| **27** | **See It from My Perspective: How Language Affects Cultural Bias in Image Understanding** | Effet de la langue sur l'orientation des jugements culturels | **Adjacente** | [arXiv](https://arxiv.org) |
| **28** | **Global Gallery: The Fine Art of Painting Culture Portraits through Multilingual Instruction Tuning** | Alignement culturel fin par instruction multilingue ciblée | **Pertinente** | [arXiv](https://arxiv.org) |
| **29** | **The discordance between embedded ethics and cultural inference in large language models** | Discordance entre éthique anglo-saxonne pré-câblée et inférence locale | **Directe** | [arXiv](https://arxiv.org) |
| **30** | **Effects of Pivot Prompting and Text Type on LLM Translation Quality for the Low-Resource ChineseVietnamese Pair** | Effet des stratégies de prompt pivot vs direct sur la cohérence | **Adjacente** | [arXiv](https://arxiv.org) |

---

## 4. Tickets Dépendants & Liens Internes à Analyser

Pour traiter ce sujet de façon unifiée dans le simulateur et l'article, il convient de croiser ce corpus avec les tickets existants du dépôt :
- [Ticket 018 — Partage de la voiture du foyer : bien partagé et rivalité](ticket_018_partage_voiture_foyer.md) : Modélisation des dialogues et arbitrages intra-foyer en français.
- [Ticket 040 — Ablation du filtre d'éligibilité des modes](ticket_040_ablation_filtre_eligibilite_modes.md) : Évaluation du rôle des contraintes physiques face au biais du LLM.
- [Ticket 055 — Benchmark multi-modèles et variabilité sous prompt factuel neutre](ticket_055_benchmark_multimodeles_et_variabilite.md) : Comportement comparé des modèles cloud et locaux face au prompt en français.
- [Ticket 068 — Mesure de la variabilité au sein d'un groupe homogène](ticket_068_variabilite_decision_groupe_homogene.md) : Décomposition de variance et détection de stéréotypes / effondrement modal.
- [Ticket 069 — Déclaration de l'usage des IA et annexe des méta-prompts](ticket_069_declaration_usage_ia_et_annexe_meta_prompts.md) : Transparence et reproductibilité des prompts pour AAMAS.

---

## 5. Plan d'Expérimentation Recommandé (Roadmap AAMAS)

1. **Ablation Bilingue de Sensibilité (FR vs EN)** :
   - Traduire fidèlement le prompt factuel neutre (Palier 1) en anglais.
   - Évaluer sur un sous-échantillon scellé représentatif ($N = 200$ agents, 600 déplacements) sur les deux juges pivots (*Gemini 3.8 Flash* et *Mistral Large*).
   - Mesurer la divergence de distribution ($L_1$, test de McNemar apparié) pour quantifier si la dérive modale dépend de la langue ou reflète un raisonnement robuste aux contraintes de transport.
2. **Mesure de l'Effet de Cadrage Culturel Explicite** :
   - Tester l'hypothèse issue de *LLMs and Cultural Values* (papier n°9) : comparer un prompt neutre générique sans mention géographique vs un prompt avec cadrage territorial explicite (Toulouse, réseau Tisséo, armature urbaine dense).
3. **Encadrement Protocolaire des Conversations Inter-Agents** :
   - Remplacer les dialogues libres non bornés par un protocole formel en 2 étapes (offre initiale d'usage de la voiture partagée $\to$ acceptation/contre-proposition sous contrainte d'horaire strict).
4. **Documentation Bilingue du Matériel Supplémentaire** :
   - Publier dans l'archive OpenReview (ZIP 25 Mo) la version originale en français de tous les prompts (`prompts.yaml`) ET leur miroir traduit en anglais avec table de correspondance terminologique.

---

## 6. Critères d'Acceptation

- [ ] L'ensemble des 30 documents du corpus Elicit est archivé et catalogué dans [`docs/paper/mémoire/`](../paper/mémoire/).
- [ ] Le ticket est consigné dans `scripts/dashboard/tickets_status.yaml` en catégorie *Expériences & Cognition*.
- [ ] Une section méthodologique dédiée dans le manuscrit (Chapitre 4 ou 5) justifie formellement le choix du français par la *validité écologique et territoriale*.
- [ ] Les résultats de l'ablation bilingue (FR vs EN) sont intégrés sous forme de test de robustesse pour désarçonner le Rebuttal AAMAS.
