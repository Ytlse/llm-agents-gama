# Analyse du Projet de Calibration de Prompt : Une Perspective de Recherche en IA

## Introduction : Le Défi de l'Alignement Distributionnel

Le projet `prompt-calibration` s'attaque à un problème fondamental et de plus en plus pertinent dans le domaine des grands modèles de langage (LLM) appliqués à la simulation sociale : l'**alignement distributionnel**. Contrairement à l'ingénierie de prompt classique qui vise à maximiser la précision sur des tâches spécifiques (par exemple, la classification ou la génération de code), l'objectif ici est de contraindre un LLM à générer des décisions dont la **distribution agrégée** réplique fidèlement une distribution de référence empirique (ici, l'enquête mobilité EMC²).

Cette problématique, parfois désignée sous le nom de *silicon sampling*, est cruciale pour la validité des simulations multi-agents basées sur des LLM. Le projet aborde cette question non pas comme un art manuel, mais comme un **problème d'optimisation formel**, en appliquant un arsenal de techniques issues de l'apprentissage automatique, de l'optimisation et de la théorie des jeux.

## Méthodologie : Un Cadre d'Optimisation Hybride

Le cœur du projet réside dans sa formulation du prompt système comme un vecteur de paramètres discrets (les "blocs" de texte) à optimiser. La recherche de la configuration optimale de ces blocs est menée via un algorithme évolutif sophistiqué.

### 1. Fonction de Perte (Loss Function)

La mesure de l'écart entre la distribution générée et la cible a évolué d'une simple distance L1 vers une fonction de perte composite plus principielle, qui respecte la nature des données sous-jacentes. Pour les dimensions **ordinales** comme l'âge ou la distance, le projet emploie l'**Earth Mover's Distance (EMD)**, ou distance de Wasserstein. [1] Cette métrique pénalise plus lourdement les erreurs entre catégories distantes (ex: 20 ans vs 60 ans) que voisines (20 ans vs 25 ans), capturant ainsi la structure ordinale que la L1 ignore. Pour les dimensions **nominales** (ex: motif de déplacement), la **Divergence de Jensen-Shannon (JSD)** est utilisée, offrant une mesure symétrique et bornée de l'écart entre distributions.

### 2. Algorithme de Recherche et Sélection de Candidats

Le projet implémente un algorithme de recherche qui s'inspire de plusieurs paradigmes d'optimisation :

*   **Stratégies Évolutives (Îlots Parallèles)** : Pour éviter les optima locaux, plusieurs populations de prompts ("îlots") sont optimisées en parallèle. [4] Des mécanismes de **migration** (échange des meilleurs candidats entre îlots) et de **crossover** (fusion de prompts parents complémentaires) permettent une exploration plus large de l'espace de recherche.

*   **Successive Halving (Racing)** : Afin d'allouer efficacement le budget d'évaluation (le coût des appels LLM), le projet utilise un algorithme de *racing*. [6, 7, 8] Plusieurs prompts candidats sont évalués sur des fractions croissantes du jeu de données. À chaque étape, les moins performants sont éliminés, concentrant ainsi les ressources sur les candidats les plus prometteurs.

*   **Gating Stratifié (Approche Ciblée)** : Une innovation notable est le "gate de strate". Avant le racing, les candidats sont d'abord évalués sur la sous-population (strate) où l'erreur est la plus grande. Seuls ceux qui améliorent cette strate spécifique sont admis au tour suivant. C'est une forme d'optimisation ciblée qui concentre l'effort là où il est le plus nécessaire.

*   **Archive de Pareto** : Le score composite agrège plusieurs dimensions. Pour gérer les compromis inhérents (un prompt peut être bon sur l'âge mais moins sur le motif), le système maintient un **front de Pareto** des solutions non-dominées. [2, 9] Cette archive sert à initialiser les îlots de manière diversifiée et à sélectionner des parents complémentaires pour le crossover.

### 3. Opérateurs de Mutation et Apprentissage par Renforcement

Les modifications du prompt ne sont pas aléatoires. Elles sont structurées en **opérateurs sémantiques** (`modify`, `insert`, `delete`, `reorder`, `merge`, `split`, `condense`). Pour choisir quel opérateur appliquer, un algorithme de **bandit manchot (UCB1)** est utilisé. [13] Chaque opérateur est un "bras" dont la récompense est l'amélioration du score. Le système apprend ainsi dynamiquement quels types de modification sont les plus efficaces.

### 4. Attribution de Crédit par Valeurs de Shapley

Pour guider les mutations, il est essentiel de savoir quelle partie du prompt (quel "bloc") contribue et comment. Le projet a dépassé la simple ablation (retrait d'un bloc à la fois), qui échoue en présence d'interactions (redondance, synergie). Il utilise désormais les **valeurs de Shapley**, un concept issu de la théorie des jeux coopératifs, pour attribuer équitablement la contribution de chaque bloc au score global. [3, 16, 17] Ceci permet d'identifier les blocs réellement utiles ou nuisibles et de guider les opérateurs de mutation de manière plus fine.

### 5. Rigueur Statistique et Reproductibilité

*   **Validation par Bootstrap** : Toute amélioration de score est validée par un test de **bootstrap apparié**. Une mutation n'est acceptée que si le gain est statistiquement significatif, ce qui prévient le surajustement au bruit d'échantillonnage des données d'évaluation.

*   **Mémoire de Leçons** : Le système apprend de ses échecs. Les raisons des rejets de mutations sont catégorisées (`[fond]` vs `[bruit]`) et synthétisées dans une "mémoire de leçons" qui est réinjectée au mutateur au tour suivant, l'empêchant de répéter des erreurs ou d'abandonner prématurément une piste prometteuse rejetée pour des raisons purement statistiques.

## Architecture et Ingénierie pour la Recherche

La robustesse du projet repose sur une architecture logicielle pensée pour la recherche expérimentale :

*   **Store SQLite Content-Addressed** : Le cœur du système est une base de données SQLite où chaque prompt, mutation et évaluation est stocké. Les prompts sont identifiés par le hash de leur contenu, formant un Graphe Orienté Acyclique (DAG) de l'historique. Ce store garantit la **reproductibilité** et la **reprise sur erreur**. Toute évaluation déjà calculée est mise en cache, rendant les exécutions idempotentes et économisant un temps et un coût de calcul considérables.

*   **Outillage Complet (CLI & Dashboard)** : Le projet est piloté par une interface en ligne de commande (`calibrate`) et accompagné d'un **dashboard Streamlit**. Ce dernier permet de visualiser en temps réel la progression des campagnes, d'explorer le DAG des prompts, d'analyser les scores et de diagnostiquer les échecs, ce qui constitue un atout majeur pour le cycle itératif de la recherche.

## Conclusion

Le projet `prompt-calibration` représente une approche mature et rigoureuse de l'ingénierie de prompt, la traitant comme un véritable problème d'optimisation en apprentissage automatique. En combinant des techniques avancées issues des algorithmes évolutifs (îlots, Pareto), de l'optimisation de hyperparamètres (Successive Halving), de l'IA explicable (valeurs de Shapley) et de l'apprentissage par renforcement (bandits), il construit un framework puissant et méthodologiquement solide.

L'accent mis sur la rigueur statistique (bootstrap, jeux de test gelés) et l'ingénierie de la reproductibilité (store content-addressed, outillage) en fait un exemple remarquable de la manière de conduire la recherche sur les LLM de façon systématique et fiable. Au-delà de son application immédiate, ce framework pourrait être généralisé à d'autres tâches d'alignement distributionnel, où l'objectif n'est pas une seule bonne réponse, mais une fidélité statistique à un phénomène du monde réel.