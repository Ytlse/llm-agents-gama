# Liste et hiérarchisation des illustrations candidates — Article court AAMAS 2027

> Document de travail pour l'arbitrage visuel de l'article court (8 pages max, budget contraint de 5 figures et 3 tableaux).  
> **Exclusions :** Les 5 figures déjà insérées dans le manuscrit compilé (`architecture_GAMA_Agents.jpg`, `ch6_echelle.png`, `ch6_distance.png`, `ch6_audit_modes.png`, `ch7_propension_quotidienne.png`) ont été retirées de cette sélection.  
> **Inclusions :** Sont intégrées les illustrations existant déjà comme fichiers dans le dépôt (notamment sous `docs/paper/figures/`) mais non insérées dans l'article court, ainsi que les visualisations conceptuelles candidates.

---

## Synthèse des 5 catégories de priorité

| Catégorie | Définition & Rôle dans l'article court | Nombre de candidates |
|---|---|:---:|
| **1. Indispensable** | Si substitution d'une figure existante : apporte la preuve directe d'un mécanisme clé de la thèse ($C_2$ ou $C_3$) | 2 |
| **2. Très utile / Fortement recommandé** | Forte valeur ajoutée explicative, format compact (1 colonne) ou Annexe prioritaire | 3 |
| **3. Utile si place disponible** | Enrichit la démonstration mais à réserver prioritairement au matériel supplémentaire (Annexes) | 5 |
| **4. Peu prioritaire** | Un court paragraphe, un tableau compact ou une formule est plus sobre et moins gourmand en espace | 5 |
| **5. Presque inutile / Déconseillé** | Décoratif, redondant, inachevé ou consommateur d'espace sans bénéfice pour un papier de 8 pages | 5 |

---

## 1. Indispensable (si substitution ou intégration compacte)

*Ces deux représentations portent directement sur les deux piliers de la thèse que le texte peine à matérialiser en prose sans surcharge.*

1. **Schéma du chemin causal de la mémoire jusqu'à la décision (§ 6.2 – § 6.4)**
   - **Type :** Flowchart horizontal compact (1 colonne ou sous-panneau de la Fig. 5).
   - **Fichier :** À concevoir / adapter depuis les traces.
   - **Pourquoi :** La thèse revendique : *« dont nous traçons le chemin jusqu'à la décision »* ($C_3$). Le texte explique que sur 4 voies possibles du passé, seul le bloc *« ce qui a changé récemment »* a transmis l'information (dans 75 des 376 prompts), tandis que le rappel RAG et la croyance consolidée sont restés muets. Un schéma causal traçant l'incident $\to$ tampon STM $\to$ bloc prompt $\to$ tirage $\to$ usure à $J+15$ est l'explication mécanistique la plus percutante du papier.
2. **Matrice du carré $2 \times 3$ hors échantillon (§ 5.3 — Ticket 103)**
   - **Type :** Grille / Heatmap compacte ($2 \times 3$ cases, format colonne).
   - **Fichier :** À générer dès stabilisation des scores du ticket 103.
   - **Pourquoi :** C'est le pivot théorique de l'article (§ 5.3) : prouver que le classifieur typé sans génération de texte égale les modèles tabulaires, et vérifier si l'effet de consigne est attaché au texte ou au modèle. Une micro-grille de 6 cellules est infiniment plus lisible et indiscutable qu'un paragraphe austère énumérant 6 valeurs composites avec intervalles de confiance.

---

## 2. Très utile / Fortement recommandé

*Visualisations déjà disponibles sur disque ou à très fort retour sur investissement cognitif. Idéales en Annexe prioritaire ou en remplacement d'une figure secondaire.*

3. **Fonction d'érosion de la mémoire et oubli exponentiel (§ 3.3)**
   - **Type :** Courbe analytique $f(t) = \exp(-t/\tau)$ modulée par la note de gravité.
   - **Fichier existant :** `docs/paper/figures/ch3_oubli.png` / `ch3_oubli.svg`.
   - **Pourquoi :** Donne le socle mathématique de la mémoire épisodique (§ 3.3) : demi-vie de base de 2,8 jours, étirée à 15,29 jours par la gravité de l'avarie (0,70). Crédibilise immédiatement le mécanisme auprès des relecteurs MAS. (Format 1 colonne, ou en tête d'Annexe).
4. **Frontière Pareto : Fidélité composite vs Coût d'inférence (§ 5.3 & § 7.1)**
   - **Type :** Scatter plot (Score composite en ordonnée inversée vs Coût en tokens / dollars en abscisse log).
   - **Fichier existant à adapter :** Dérivable de `docs/paper/figures/familles_composite_l1_nuage.png`.
   - **Pourquoi :** Rend tangible l'argument économique massue : le classifieur typé divise le coût par cinquante (1,06 \$ vs 49,28 \$ pour 23 026 décisions) tout en logeant son composite dans la bande tabulaire.
5. **Dynamique des opinions déclarées aux 4 jalons (§ 6.3 & § 6.4)**
   - **Type :** Séries temporelles discrètes sur échelle de Likert (0 à 10).
   - **Fichier existant :** `docs/paper/figures/tmp_ch7_affinites_tous_modes.png` / `tmp_ch7_affinites_tous_modes.svg`.
   - **Pourquoi :** Montre que la perception de sécurité de la voiture chute de 8 à 3 puis revient à sa valeur initiale, alors que la question témoin (écologie) reste stable à 3. Preuve éclatante de la rationalité perçue de l'agent.

---

## 3. Utile si place disponible (Destination naturelle : Annexes)

*Contenus informatifs et rigoureux, mais dont la présence dans les 8 pages du corps surchargerait la mise en page.*

6. **Trajectoire de confiance de la croyance voiture (§ 6.2 & § 6.4)**
   - **Type :** Courbe d'évolution de la confiance du concept.
   - **Fichier existant :** `docs/paper/figures/tmp_ch7_croyances_voiture.png` / `tmp_ch7_croyances_voiture.svg`.
   - **Pourquoi :** Explique pourquoi l'extinction s'est produite par *usure* et non par *contradiction* (la croyance n'ayant jamais été servie, zéro contradiction n'a été enregistrée). Excellent pour l'Annexe sur l'adaptation.
7. **Audit unitaire découpé par tranche de distance (§ 5.4)**
   - **Type :** Histogramme groupé / courbes d'exactitude selon la distance du trajet.
   - **Fichier existant :** `docs/paper/figures/ch6_audit_distance.png` / `ch6_audit_distance.svg`.
   - **Pourquoi :** Complète la Fig. 4 en montrant comment l'erreur individuelle varie sur les trajets de proximité (< 1 km) vs moyenne distance. À placer dans l'Annexe sur l'audit unitaire.
8. **Schéma conceptuel de la cascade à 3 étages (§ 7.1)**
   - **Type :** Diagramme de flux décisionnel (Étage 1 Déterministe $\to$ Étage 2 Nominal typé/tabulaire $\to$ Étage 3 Délibératif sur rupture).
   - **Fichier :** À concevoir.
   - **Pourquoi :** Très élégant pour la discussion d'ouverture du § 7.1, mais comme cette architecture n'est *ni construite ni mesurée* dans l'article, une figure en corps de texte risquerait d'attirer des critiques sur l'absence de mesures de flux.
9. **Profils modaux selon les strates socio-démographiques (§ 5.2)**
   - **Type :** Graphiques à barres empilées par strate (distance, motif, statut).
   - **Fichiers existants :** `docs/paper/figures/ch99_modes_distance.png`, `ch99_modes_motif.png`, `ch99_modes_occupation.png`.
   - **Pourquoi :** Illustre la décomposition de la métrique composite et documente visuellement les strates rebelles (ex. pic TC des 15–19 ans). Indispensable pour l'Annexe F.
10. **Représentativité des 13 marges synthétiques vs Enquête EMC² (§ 4.1)**
    - **Type :** Graphique d'équivalence en barres horizontales avec intervalle d'équivalence $\pm 1$ pt.
    - **Fichier :** À générer depuis `docs/paper/article-court/sections/04_bench.fr.md`.
    - **Pourquoi :** Démontre la conformité stricte de la cohorte synthétique du banc $C_1$. Comme tous les écarts sont minuscules ($\le 0,50$ pt), un tableau en Annexe A suffit, mais un graphique d'équivalence en annexe est très visuel.

---

## 4. Peu prioritaire (Le texte ou un tableau compact suffit)

*Éléments dont le coût spatial en figure excède largement le gain d'information.*

11. **Barres comparatives Composite vs L1 global (§ 5.1)**
    - **Type :** Histogrammes doubles par famille de modèles.
    - **Fichier existant :** `docs/paper/figures/familles_composite_l1_barres.png` / `familles_composite_l1_barres.svg`.
    - **Pourquoi :** Fait doublon avec la Fig. 2 (axe composite) et le Tableau 1. Consomme de l'espace vertical pour répéter des scores déjà tabulés.
12. **Nombre absolu de trajets en voiture par jour (§ 6.4)**
    - **Type :** Bâtons journaliers bruts.
    - **Fichier existant :** `docs/paper/figures/tmp_ch7_voiture_par_jour.png` / `tmp_ch7_voiture_par_jour.svg`.
    - **Pourquoi :** Beaucoup moins informatif que la propension quotidienne (Fig. 5), car pollué par les variations d'emploi du temps (jours avec 2 trajets vs jours avec 5 trajets).
13. **Schéma du protocole expérimental en 3 règles (§ 4.2)**
    - **Type :** Boîtes de workflow méthodologique (21 variables $\to$ distribution $\to$ renormalisation).
    - **Fichier :** À concevoir.
    - **Pourquoi :** Les 3 règles sont énoncées en 10 lignes limpides au § 4.2. Un schéma ne ferait que paraphraser le texte sans ajouter de données.
14. **Processus d'optimisation réflexive du prompt expert (§ 4.4)**
    - **Type :** Organigramme de boucle de mutation (diagnostic par strate $\to$ hypothèse $\to$ réécriture $\to$ validation sans seuil).
    - **Fichier :** À concevoir.
    - **Pourquoi :** Relève de la méthodologie de calibration ; le texte du § 4.4 et le prompt en Annexe D fournissent déjà toute la matière nécessaire.
15. **Comparaison chronologique inter-campagnes (`comparaison_experiences`)**
    - **Type :** Graphique d'historique de versions.
    - **Fichier existant :** `docs/paper/figures/comparaison_experiences.png`.
    - **Pourquoi :** Outil de travail interne pour les auteurs, sans pertinence pour le lecteur scientifique qui n'évalue que la campagne scellée finale.

---

## 5. Presque inutile / Déconseillé

*À proscrire absolument du corps de texte (gaspillage de place, confusion ou risque de pénalisation lors de la relecture).*

16. **Carte géographique / SIG du réseau toulousain (`toulouse_transport_system`)**
    - **Type :** Plan SIG des 453 communes et réseaux structurants.
    - **Fichier existant :** `docs/paper/figures/toulouse_transport_system.png`.
    - **Pourquoi :** Pure figure décorative de remplissage. AAMAS est une conférence d'IA et de systèmes multi-agents, pas une revue de géographie ou d'aménagement local.
17. **Grille des 20 signes pour l'expérience de presse (§ 6.4 & § 7.3)**
    - **Type :** Matrice d'analyse sémantique.
    - **Fichier existant :** `docs/paper/figures/ch7_grille_signes.png` / `ch7_grille_signes.svg`.
    - **Pourquoi :** L'expérience de presse est explicitement mentionnée comme *en cours* et sans résultats consolidés dans le texte court. Publier une grille d'évaluation vide de résultats empiriques invite les reviewers à sanctionner un travail inachevé.
18. **Analyse des résidus d'ajustement (`ch6_residu`)**
    - **Type :** Graphique multidimensionnel de résidus statistiques.
    - **Fichier existant :** `docs/paper/figures/ch6_residu.png` / `ch6_residu.svg`.
    - **Pourquoi :** Très lourd visuellement, difficile à interpréter rapidement, et sans message clair pour un article court.
19. **Graphique de la fuite de cible à 93,4 % d'exactitude (§ 5.4)**
    - **Type :** Matrice de confusion ou courbe de performance sur variable endogène.
    - **Fichier :** À concevoir.
    - **Pourquoi :** Il s'agit d'une mise en garde méthodologique sur un modèle abandonné (distance issue du temps déclaré). Trois phrases percutantes suffisent largement ; lui accorder une figure induirait le lecteur en erreur.
20. **Diagramme de répartition modale brute globale (camembert / histogramme global)**
    - **Type :** Donut chart ou barres 4 modes (Voiture, TC, Marche, Vélo).
    - **Fichier :** À concevoir.
    - **Pourquoi :** La part modale brute globale masque toutes les distorsions locales et individuelles. C'est précisément la faiblesse dénoncée dans le papier pour justifier le composite stratifié (Fig. 2) et l'audit unitaire (Fig. 4).
