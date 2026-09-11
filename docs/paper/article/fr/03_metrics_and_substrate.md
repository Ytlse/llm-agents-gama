# 3. Métriques et socle d'évaluation (brouillon)

<!-- Dernière mise à jour : 2026-09-10 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), § 2, Étape 0 — « Étape 0 : Définition des Métriques & Validation Démographique ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

### 2.1 Cadre de Mesure et Métriques d'Évaluation
Pour évaluer rigoureusement les modèles sur les deux échelles décisionnelles :

1. **Métriques Macroscopiques (Agrégées)** :
   * **Parts Modales ($\hat{P}_m$)** : Proportion de choix pour chaque mode $m \in \{\text{Voiture}, \text{Marche}, \text{TC}, \text{Vélo}\}$.
   * **Erreur L1 Cumulée** : $\text{L1} = \sum_{m} |\hat{P}_m - P_m^{\text{EMC2}}|$.
   * **Score Composite $S$** : Combinaison de la déviation L1 et des pénalités de dispersion inter-runs.

2. **Métriques Microscopiques (Individuelles sur jeu scellé $N = 13\,045$ trajets)** :
   * **Accuracy Globale** : Taux de prédiction exacte de la modalité observée.
   * **Rappel & Précision par Mode** : Performance par catégorie modale.
   * **LogLoss Multi-Classe** : Qualité de la calibration des probabilités modales.

### 2.2 Validation Démographique de la Population Synthétique ($N = 1\,000$ agents)
Dans notre simulation multi-agents GAMA, chaque agent est un **individu virtuel équiprobable** (poids unitaire = 1). La population synthétique est générée par le pipeline EQASIM à partir du Recensement Insee RP 2022, des revenus FILOSOFI et de l'enquête ménages-déplacements.

La cohorte contrôlée est la **population scellée v3** (`data/population/population_1000_AAMAS_v3/`, sha256 `8d8bfa36…` ; 1 000 personas en 514 ménages entiers, tirés par sélection stratifiée dans un vivier eqasim de 11 922 personnes). Chaque cible porte sa source : la page du rapport AUAT/CEREMA « Enquête mobilité 2023 — bassin de vie toulousain », ou un recalcul sur les microdonnées ProGEDO (COEP, 5 ans et +) gelé dans le dépôt quand le rapport ne publie pas la marge. Mesure : `scripts/AAMAS/control_population.py`, trace `docs/traces/2026-09-03_01-18_controle_toulouse_population_1000_AAMAS/`.

| Dimension démographique | Cible (source) | Cohorte scellée v3 ($N = 1\,000$) | Écart ($\Delta$) | Statut (TOST $\pm 1$ pt, IC95) |
|---|---|---|---|---|
| **Genre (Femmes / Hommes)** | 51,3 % / 48,7 % *(recalcul microdonnées — non publié)* | 51,3 % / 48,7 % | $0,0\text{ pt}$ | **Conforme** |
| **Âge : 5-17 ans** | 16 % *(rapport p. 11)* | 17,2 % | $+1,2\text{ pt}$ | **Conforme** |
| **Âge : 18-24 ans** | 13 % *(p. 11)* | 11,9 % | $-1,1\text{ pt}$ | **Conforme** |
| **Âge : 25-34 ans** | 14 % *(p. 11)* | 14,4 % | $+0,4\text{ pt}$ | **Conforme** |
| **Âge : 35-49 ans** | 22 % *(p. 11)* | 21,9 % | $-0,1\text{ pt}$ | **Conforme** |
| **Âge : 50-64 ans** | 19 % *(p. 11)* | 18,5 % | $-0,5\text{ pt}$ | **Conforme** |
| **Âge : 65 ans et plus** | 16 % *(p. 11)* | 16,1 % | $+0,1\text{ pt}$ | **Conforme** |
| **Ménages sans voiture** | 19 % *(p. 21, base ménage)* | 21,4 % *(personas pondérés 1/taille)* | $+2,4\text{ pt}$ | **Conforme** (écart non établi) |
| **Ménages à 1 voiture** | 45 % *(p. 21)* | 44,2 % | $-0,8\text{ pt}$ | **Conforme** |
| **Ménages à 2 voitures et +** | 35 % *(p. 21)* | 34,4 % | $-0,6\text{ pt}$ | **Conforme** |
| **Permis de conduire (18 ans et +)** | 85,9 % *(recalcul microdonnées — non publié)* | 85,9 % | $0,0\text{ pt}$ | **Conforme** |
| **Personnes sans déplacement la veille** | 10,6 % *(recalcul microdonnées)* | 10,6 % | $0,0\text{ pt}$ | **Conforme** |

Les treize marges du contrôle sont conformes (les cinq non reproduites ici : couronne de résidence, croisement couronne × motorisation, occupation, taille de ménage, abonnement TC, type de logement), aucune n'est « non mesurable ».

**Ce que ce tableau établit, et ce qu'il n'établit pas.** Douze marges sur treize sont *allouées* par la sélection stratifiée — leur conformité mesure la règle, pas le générateur ; seule la motorisation en base ménage est conforme sans allocation. La fidélité du générateur se lit sur le vivier de 11 922 personnes (9 marges hors tolérance : 3ᵉ couronne $-5,2$ pt, immobiles 15,1 % contre 10,6, actifs à temps partiel $+2,4$ pt). Deux précautions accompagnent cette lecture :

1. **Ces marges sont calées par construction.** Le moteur de synthèse amont ajuste directement la fréquence des profils sur ces distributions ; les retrouver est un **contrôle de cohérence de la chaîne de génération**, non une preuve de fidélité sociologique. Ce qui reste à tester est ailleurs : dans les **croisements** (âge × motorisation × zone fine), là où une synthèse par marges peut échouer sans qu'aucune marge ne bouge.
2. **Un test du $\chi^2$ non significatif ne prouve pas la conformité** : il échoue à détecter un écart, ce qui n'est pas la même chose. À $N = 1\,000$ sa puissance est faible, et un « seuil de non-rejet $p > 0,95$ » n'est pas un critère statistique. La formulation retenue pour la publication est donc un **test d'équivalence** (TOST) marge par marge, avec une borne d'indifférence annoncée d'avance ($\pm 1$ pt), complété par l'écart absolu maximal et un $V$ de Cramér comme tailles d'effet.

### 2.3 Dimensionnement de l'Échantillon ($N = 1\,000$) et Justification Statistique
Le choix de fixer l'évaluation principale sur une cohorte de $N = 1\,000$ agents synthétiques (stratifiés selon secteur $\times$ classe d'âge $\times$ motorisation) répond à une justification statistique rigoureuse (*ex ante*, détaillée dans [`JUSTIFICATION_TAILLE_ECHANTILLON.md`](../../methode/JUSTIFICATION_TAILLE_ECHANTILLON.md)) :

1. **Unité d'analyse = déplacement et effet de grappe ($n_{\text{eff}}$) :**  
   Une part modale se calcule sur les flux de trajets ($\approx 3{,}5$ déplacements/jour/agent, soit $\approx 3\,500$ déplacements pour $1\,000$ agents). Compte tenu de la corrélation intra-agent (même équipement automobile, même domicile/travail, $\rho \approx 0{,}4 - 0{,}5$), l'effectif efficace équivalent est de $n_{\text{eff}} \approx 1{,}75 \times N \approx 1\,750$ déplacements indépendants. Tout intervalle de confiance est estimé par **cluster bootstrap par agent**.
2. **Plancher de l'enquête terrain (EMC² 2023) :**  
   L'enquête de référence toulousaine porte sur $\approx 16\,000$ habitants et présente, après redressement et grappes ménages, une incertitude propre de $\pm 0{,}3$ à $\pm 0{,}6\text{ pt}$ sur les parts modales. Réduire l'incertitude simulée en deçà n'apporte aucun pouvoir de décision statistique face à une cible dont la précision est finie.
3. **Détection de biais structurels ($> 8\text{ pt}$) :**  
   À $N = 1\,000$ ($n_{\text{eff}} \approx 1\,750$), la demi-largeur de l'IC à $95\,\%$ est de $\pm 2{,}0\text{ pt}$ sur la marche et $\pm 1{,}0\text{ pt}$ sur le vélo. Cette précision suffit amplement à caractériser les biais systématiques observés (sous-estimation de la marche, engouement disproportionné pour le vélo) et à autoriser l'analyse sur 3–4 macro-strates spatiales et socio-démographiques.
4. **Arbitrage du budget d'inférence :**  
   Au-delà de $N \approx 2\,000$, l'incertitude d'échantillonnage ($\pm 1{,}5\text{ pt}$) devient négligeable devant les biais inhérents de spécification méthodologique (règle du mode principal, seuils de micro-déplacements : $3$ à $5\text{ pts}$). Le budget de calcul est ainsi réalloué à la **mesure de la variabilité stochastique (5 graines)** et aux **plans appariés intra-agents (McNemar)** sur les scénarios d'actualité et d'hystérésis ($500$ à $1\,000$ agents ré-interrogés dans 5 conditions).

La stabilité par changement d'échelle ($N = 1\,000 \to 10\,000$) découle du tirage stratifié et se vérifie par la même procédure.

---
