# 5. Évaluation sous prompt factuel neutre et circonstancié et variabilité (brouillon)

<!-- Dernière mise à jour : 2026-09-13 -->

**Document :** brouillon français du chapitre 5 de l'article AAMAS 2027.
**Statut :** `brouillon v0.2` (13 septembre 2026) — définition formelle du prompt factuel neutre et circonstancié (persona complet et trajets physiques détaillés, sans ingénierie décisionnelle) ; benchmark multi-modèles actualisé selon la plateforme *Pilotage llm-agents-gama* ; protocole d'évaluation de la variabilité à température strictement nulle ($\tau = 0,0$). Renumérotation canonique en 5.1, 5.2, 5.3. Ni maître anglais ni rendu LaTeX à ce stade (règle de fabrication : le français d'abord).
**Place dans l'article :** section 5 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

### 5.1 Définition du Prompt Factuel Neutre et Circonstancié (Palier 1)

Le premier palier d'évaluation (Palier 1) soumet les modèles de fondation génériques à un **prompt factuel neutre et circonstancié**. L'objet de l'évaluation porte ici sur la capacité décisionnelle intrinsèque de modèles pré-entraînés standards (sur étagère, sans ajustement supervisé), placés dans des conditions d'information riches mais dépourvues de tout guidage heuristique.

Le prompt soumis au modèle associe deux blocs descriptifs complets et rigoureusement structurés :
1. **Une description complète du persona** : le vecteur sociologique complet de l'individu (sexe, tranche d'âge, catégorie socio-professionnelle, composition du ménage, niveau de revenu, motorisation, détention du permis et abonnements aux réseaux de transport collectif), ses motifs de déplacement et ses contraintes d'agenda glissant sur la journée (activités chaînées).
2. **Une description précise et exhaustive de l'offre d'itinéraires** : pour chaque déplacement, les options physiquement calculées par les moteurs de réseau — trajets directs (marche, vélo, voiture individuelle) issus du calcul de plus court chemin sur le graphe routier OpenStreetMap, et trajets en transport en commun issus du calculateur OpenTripPlanner (OTP) sur les grilles horaires réelles — avec le détail de chaque étape (durée de marche d'accès et de diffusion, temps d'attente à l'arrêt, correspondances, temps à bord).

Ce qui fonde la spécificité de ce **Palier 1 d'ablation**, c'est **l'absence totale d'ingénierie incitative ou décisionnelle** (*zero prompt engineering*). Aucune heuristique d'arbitrage situationnel (telle que des principes explicites sur l'effort, la pénibilité de la marche, le confort ou la valeur du temps), aucune consigne d'alignement comportemental et aucun exemple démonstratif (*few-shot*) ne sont injectés dans le contexte. La consigne est strictement fonctionnelle et neutre :
> *« Sélectionner le mode de déplacement optimal en tenant compte du persona. Analyse le profil. N'élimine aucune option : attribue à CHAQUE option proposée, par son index, la probabilité en % que ce persona la retienne [...]. La somme doit valoir exactement 100. Justifie la répartition en une phrase concise. »*

Cette condition isole ainsi le comportement décisionnel intrinsèque des LLMs pré-entraînés face aux contraintes physiques et sociologiques réelles d'une métropole, avant toute tentative d'optimisation ou de guidage sémantique (Palier 2).

### 5.2 Benchmark Multi-Modèles et Diversité des Voies d'Inférence

Afin de garantir que les résultats observés ne constituent pas un artefact propre à un fournisseur ou à une famille d'architectures, le benchmark confronté au prompt factuel neutre et circonstancié couvre l'ensemble des voies d'inférence orchestrées par la plateforme *Pilotage llm-agents-gama* :

1. **Modèles propriétaires distants (API cloud)** :
   * **Google Gemini** : `gemini-3.1-flash-lite` (juge de référence stabilisé de l'évaluation, seuil de quota journalier appliqué), `gemini-3.5-flash-lite` (variante de génération suivante), et `gemini-3.8-flash`.
   * **Mistral AI** : `mistral-small-latest` (inférence souveraine européenne, 60 req/min) et `mistral-large-2512` (modèle frontière à grand contexte, 30 req/min).
2. **Modèles ouverts managés à haut débit (Inférence LPU Cloud)** :
   * **Qwen** : `qwen/qwen3.6-27b` et `qwen/qwen3.8-27b` (servis via l'infrastructure Groq).
   * **Grands modèles ouverts** : `gpt-oss-120b` (servi via Cerebras et Groq) et famille **Google Gemma** (`gemma-4-31b` via Cerebras, `gemma-4-26b-a4b-it` et `gemma-4-31b-it` via Google).
3. **Inférence locale déterministe sur poids ouverts (LM Studio sur machine hôte)** :
   * Exécutés localement via un adaptateur standardisé OpenAI-compatible (`http://host.docker.internal:1234/v1`), garantissant l'indépendance intégrale vis-à-vis des quotas externes et la souveraineté absolue des données de mobilité :
     * Famille **Qwen** : `qwen/qwen3.8-27b` (quantifié MLX 4-bit, 27B, contexte 262k), `qwen3-vl-8b-instruct-mlx`, `qwen3-vl-32b-instruct-mlx`.
     * Famille **Mistral** : `mistralai/mistral-small-3.2` (24B, 4-bit), `mistralai/mistral-nemo-instruct-2407` (12B), `mistralai/mistral-7b-instruct-v0.3` (7B).
     * Modèles compacts et exploratoires : `google/gemma-4-e4b` (4B effectifs), `meta/muse-glimmer` (28B).
4. **Décideur autonome Antigravity (sous-agents sans quota d'API)** :
   * Exécution par délégation directe à des sous-agents autonomes via un protocole IPC local (`gemini-3.8-flash`, `claude-opus-4.6`), permettant de dérouler des expériences complètes sur la cohorte scellée sans dépendance aux quotas de requêtes externes.

Tous ces modèles sont soumis au même contrat unifié d'évaluation (mêmes 21 variables, même ordre randomisé des options OTP/OSM, même schéma de sortie JSON probabiliste).

### 5.3 Protocole de Variabilité et Dispersion Inter-Runs à Température $\tau = 0,0$

Toutes les évaluations de la campagne ont été conduites à **température strictement nulle ($\tau = 0,0$)**, sous décodage glouton (*greedy decoding*), afin de maximiser le déterminisme des réponses.

Toutefois, sur les architectures modernes de LLM — en particulier les modèles à mélange d'experts (*Mixture-of-Experts* - MoE) ou distribués sur clusters d'accélérateurs —, l'inférence à $\tau = 0,0$ peut présenter une variance résiduelle inter-runs induite par la non-associativité des opérations en virgule flottante lors du traitement par lots dynamiques (*dynamic batching*) ou par des arbitrages de routage interne.

> **(NOTE — MESURER LA VARIABILITÉ À TEMPÉRATURE 0)** : Mesurer empiriquement la variabilité résiduelle inter-runs à température strictement nulle ($\tau = 0,0$) sur 5 exécutions indépendantes de la cohorte scellée ($N = 1\,000$ personnes, 3 299 déplacements). Il convient de quantifier la dispersion réelle des parts modales agrégées (écart-type $\sigma$) et le taux de bascule individuelle inter-runs, afin de valider par la mesure l'amplitude du non-déterminisme résiduel plutôt que d'extrapoler un encadrement a priori.

Pour encadrer et publier cette incertitude de façon réfutable :
* Chaque condition est répétée sur 5 graines aléatoires fixées (`seeds = [0, 42, 123, 999, 2026]`) pour les tirages stochastiques résiduels et l'ordonnancement des options.
* Nous mesurons l'écart-type $\sigma$ des parts modales et calculons les intervalles de confiance à $95\,\%$ par rééchantillonnage par grappe (*cluster bootstrap* au niveau agent, conformément au protocole de la section 4.5).
* Les résultats d'audit mesureront si la distribution agrégée reste stable (emplacement **[xx]** pt d'écart maximal) et documenteront la dispersion réelle.
* Nous publions en outre le **taux de bascule individuelle** inter-runs — part des décisions dont le mode retenu change d'une exécution à l'autre pour un même persona et un même déplacement. Une part modale agrégée stable peut en effet masquer des permutations individuelles, critiques pour l'affectation sur un réseau de transport.
* Toute comparaison statistique entre deux conditions de prompt est conduite par **test de McNemar sur les décisions appariées** (terme à terme sur chaque décision unitaire d'un même individu face aux mêmes options), écartant tout artefact lié à des exactitudes globales trompeuses sur populations disjointes.

---

### Tickets associés à ce chapitre
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — Synthèse du benchmark multi-modèles et variabilité inter-graines sous prompt factuel neutre
