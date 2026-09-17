# 5. Protocole de calibration du choix modal

<!-- Dernière mise à jour : 2026-09-17 -->

**Document :** chapitre 5 de l'article AAMAS 2027 — le chapitre de **protocole** : il définit les conditions comparées, le chapitre 6 dit ce que la comparaison établit.
**Statut :** `brouillon v0.10` (17 septembre 2026) — le titre devient descriptif : « Quatre façons de choisir, une seule information » annonçait une égalité d'information que le contrat du § 4.3 n'établit pas, celui-ci égalisant les 21 variables et non l'information dont chaque décideur dispose. Le § 5.3.5 publie le texte intégral du prompt expert de référence (`prompt_expert_05`), comme le § 5.1 publie celui du prompt minimal.
**Statut antérieur :** `brouillon v0.9` (16 septembre 2026) — reformulation selon les standards d'exigence AAMAS : formalisation mathématique de la calibration discrète sous contraintes au § 5.3, cadrage micro-comportemental au sein du système multi-agent, élimination des plaidoyers défensifs, et mise en conformité avec les règles de style (`make paper-style`).
**Statut antérieur :** `brouillon v0.8` (16 septembre 2026) — le fil rouge du chapitre est repris. Le chapeau pose la question du chapitre, jusqu'où un agent isolé de son environnement produit un comportement proche du réel, et dit que le protocole est une phase de calibration : régler le décideur sur le cas isolé et mesurable pour que la population reste représentative une fois replacée dans la simulation complète. Le § 5.1 dit ce que le prompt porte en propre face aux modèles de référence. Le § 5.2 est nouveau : le benchmark multi-modèles revient d'ameliorations.md, non plus en catalogue de fournisseurs mais comme raison de mesurer plusieurs modèles, avec sa note « à compléter ». Le prompt réglé devient le § 5.3, les bornes le § 5.4 et l'audit le § 5.5. Le § 5.4 cesse de chiffrer planchers et plafond : le § 4.4 publie les méthodes de référence et le § 6.1 le tableau complet, un chapitre de protocole définit les bornes et ne les mesure pas. Le vocabulaire des paliers sort du corps du texte au profit du nom des conditions.
**Place dans l'article :** section 5 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). Trame : [`../plan/PLAN.md`](../plan/PLAN.md). État d'avancement : [`../README.md`](../README.md).

---

L'intégration d'agents fondés sur des modèles de langue dans une simulation multi-agents de mobilité urbaine pose une exigence de calibration micro-comportementale. Dans le modèle complet décrit au chapitre 3, les agents interagissent à travers un environnement dynamique contraignant : congestion du réseau viaire sous GAMA, saturation des lignes de transport collectif et couplages temporels stricts imposés par la chaîne des véhicules personnels. Pour que les dynamiques macroscopiques émergentes de la simulation soient fidèles à la réalité d'un territoire, la politique locale de décision de chaque agent individuel doit être représentative de la population modélisée.

Ce chapitre formalise le protocole expérimental conçu pour isoler, calibrer et évaluer cette politique locale de choix modal avant son déploiement dans le simulateur interactif. Isoler l'agent signifie ici soumettre son mécanisme de décision à une situation de choix unitaire : un déplacement précis, caractérisé par un profil sociologique, une offre multimodale calculée et des conditions météorologiques, sans historique dynamique de la journée écoulée. L'objectif de cette phase de calibration est d'ajuster l'arbitrage qualitatif du décideur afin que la distribution de ses choix reproduise les régularités observées dans l'enquête ménages-déplacements, sans dégrader sa transférabilité.

Quatre conditions décisionnelles sont comparées à entrées égales, selon le contrat d'évaluation du § 4.3 :
1. Les planchers statistiques et heuristiques physiques : des règles de référence sans information comportementale (hasard uniforme, prédiction majoritaire zero-rule, heuristique de durée minimale du réseau).
2. Le prompt minimal : le modèle de langue recevant les faits situationnels exhaustifs sans aucune consigne d'arbitrage (zero-shot descriptive).
3. Le prompt expert : le modèle guidé par des heuristiques de raisonnement optimisées sous contraintes qualitatives strictes.
4. Les modèles tabulaires supervisés : quatre algorithmes statistiques de référence ajustés directement sur les microdonnées de l'enquête.

Le § 5.1 détaille la spécification du prompt minimal et publie un cas d'inférence intégral. Le § 5.2 expose le benchmark multi-modèles garantissant l'invariance architecturale. Le § 5.3 formalise mathématiquement le problème de calibration discrète de prompt et détaille ses garde-fous contre le sur-apprentissage. Le § 5.4 borne l'espace des performances entre planchers heuristiques et plafond tabulaire. Enfin, le § 5.5 décrit le protocole d'audit à parité de terrain évaluant l'exactitude désagrégée sur les déplacements réels de l'enquête.

## 5.1 Le prompt minimal (détail du persona + options d'itinéraire)

La condition de base évalue des modèles de fondation génériques, utilisés sur étagère sans réentraînement supervisé, face à un prompt minimal et circonstancié. Cette condition mesure la capacité décisionnelle native du modèle face à un état descriptif riche, en l'absence totale d'orientation stratégique.

Pour chaque décision $i$, l'état soumis au modèle est un quadruplet $s_i = (x_i, \mathcal{O}_i, \mathcal{A}_i, \mathcal{W}_i)$ :
1. Le vecteur sociologique du persona ($x_i$) : âge, sexe, catégorie socio-professionnelle, taille et composition du ménage, classe de revenu, motorisation, détention du permis et abonnements aux transports publics.
2. L'offre multimodale d'itinéraires ($\mathcal{O}_i$) : ensemble des options physiquement calculées pour le déplacement. Les trajets individuels (marche, vélo, voiture) proviennent du plus court chemin sur le graphe OpenStreetMap ; les trajets en transport collectif sont calculés par OpenTripPlanner sur les grilles de service réelles, incluant le détail des étapes (accès, attente, correspondances, trajet à bord).
3. L'agenda prévisionnel de la journée ($\mathcal{A}_i$) : enchaînement des activités restantes et des distances associées jusqu'au retour final au domicile.
4. Le contexte météorologique ($\mathcal{W}_i$) : conditions au moment du départ et prévisions pour les tranches horaires ultérieures.

L'instruction système se limite strictement à la définition de la tâche et au format d'émission de la décision :

> *Select the optimal travel mode taking the persona into account.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variante prompt_minimal_02 (82 mots, famille « minimale », audit de neutralité conforme du 2026-09-14) ; le schéma JSON attendu suit la consigne et est reproduit en annexe -->

Un cas concret d'inférence illustre la structure du signal reçu par le modèle :

```
--- agent_id=1320713 | Destination: work | Departure: 08:16 ---
**Context:** Weather: 10°C, Clear/Sunny. Today 10°C to 22°C, sunrise 06:27,
sunset 21:15. No precipitation expected.
**Weather later:** afternoon 15°C, Clear/Sunny · evening 16°C, Clear/Sunny.
Frédéric-Adrien, 28, Full-Time Worker (household of 2, very low income).
Usual trip purposes: Work. Lives in: Toulouse

**Further trips planned today:**
    · 13:32 → other (≈12.4 km)
    · 16:27 → home (≈11.5 km)
    · 20:00 → leisure (≈15.1 km)

**Trip options** (5 options, indices 0 to 4):
- [0] foot,metro,foot: Travel time: 20 minutes, including 16 minutes of walking.
      Has a public transport pass.
    · Walk to 'Marengo-SNCF': 9 minutes.
    · Metro 'A' to 'Esquirol': 4 minutes.
    · Walk to 'work': 7 minutes.
- [1] foot: Estimated duration: 26 minutes. Distance: 2.0 km.
- [2] bicycle: Estimated duration: 11 minutes. Distance: 2.2 km.
- [3] foot: Travel time: 28 minutes, including 28 minutes of walking.
    · Walk to 'work': 28 minutes.
- [4] car: Estimated duration: 11 minutes. Distance: 3.0 km.
```

Réponse retournée par le modèle :

```json
[{"agent_id": "1320713",
  "probabilities": [
    {"index": 0, "mode": "foot,metro,foot", "probability": 20.0},
    {"index": 1, "mode": "foot",            "probability":  5.0},
    {"index": 2, "mode": "bicycle",         "probability": 50.0},
    {"index": 3, "mode": "foot",            "probability":  5.0},
    {"index": 4, "mode": "car",             "probability": 20.0}],
  "reason": "Frédéric-Adrien favors the fast 11-minute bicycle ride to save time
             on a tight schedule while keeping costs low, bypassing a slow walk."}]
```

<!-- source: bloc reçu et réponse — data/experiences/exp_gemini-35-fl_proexp04_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim/executions/2026-09-15_05_18_34/decisions.jsonl, person_id 1320713.
⚠ CAS À REPRENDRE AVANT PUBLICATION, et en entier. (1) Le départ de ce déplacement est résolu au 17 mars : c'est un des 866 cas que le ticket 088 a datés du lendemain, son offre d'itinéraires a donc été calculée pour le mauvais jour. (2) La réponse citée vient du décideur sous prompt expert, celui du palier 1 n'ayant pas de score sur la v6. Bloc reçu ET réponse sont à reprendre d'un décideur prompt_minimal_02 rejoué sur le jeu corrigé (ticket 088 § 3.4). -->

Le modèle reçoit cinq options pour un trajet de deux kilomètres, comprenant deux cheminements pédestres et une option combinant marche et métro. En l'absence de directive sur la pénibilité relative de la marche, la valeur du temps ou l'impact météorologique, le modèle distribue sa masse de probabilité sur les options disponibles. C'est cette distribution continue qui est scorée selon le contrat du § 4.3.

## 5.2 Le benchmark : les mêmes faits, plusieurs modèles

Afin de distinguer les caractéristiques fondamentales du cadre décisionnel des artéfacts propres à une architecture d'inférence donnée, le protocole soumet le prompt minimal et le prompt expert à une batterie de modèles hétérogènes. Le jeu de test, les contextes d'agents et la randomisation de l'ordre des options demeurent strictement invariants d'un modèle à l'autre.

| Fournisseur | Modèle | Prompt neutre | Prompt réglé |
|---|---|:--:|:--:|
| Google | `gemini-3.1-flash-lite` | mesuré | mesuré |
| Google | `gemini-3.5-flash-lite` | **[xx]** | mesuré |
| Mistral | `mistral-large-2512` | mesuré | mesuré |

<!-- sources: data/experiences/exp_{gemini-31-fl,gemini-35-fl,mistral-l-25}_{promin02,proexp05,proexp06,proexp08}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim, exécutions du 2026-09-15 ; proexp04 retiré de cette liste le 2026-09-17, la variante ayant été supprimée du dépôt. Les scores vont au chapitre 6. [xx] : le décideur gemini-3.5-flash-lite sous prompt minimal est en file de campagne, et sera de toute façon rejoué sur le jeu corrigé du ticket 088. -->

⚠ **Benchmark à compléter.** Deux fournisseurs et trois modèles documentent la faisabilité mais ne constituent pas une couverture universelle. Les décideurs intégrant la famille Claude sont déclarés et en cours d'exécution ; un modèle de la famille OpenAI est programmé. Les conclusions tirées qualifient les architectures mesurées et ne prétendent pas s'étendre sans vérification à l'ensemble des modèles de langue.

## 5.3 Le prompt expert : optimisation discrète sous contraintes cognitives

L'évaluation du prompt minimal fait apparaître des distorsions systématiques dans la distribution des choix selon les strates de population. Pour réduire ces écarts sans dégrader la robustesse de l'agent, le prompt système fait l'objet d'un processus d'optimisation structuré, guidé par la fonction de perte composite définie au § 4.2.

### 5.3.1 Formulation mathématique de la calibration

Soit $\Pi$ l'espace des prompts textuels admissibles. Un prompt $p \in \Pi$ paramètre la politique locale d'un agent $\pi(\cdot \mid s_i; p)$, qui associe à tout état perçu $s_i$ une distribution de probabilité sur les modes disponibles $\mathcal{M}(\mathcal{O}_i)$.

Pour une sous-population $\mathcal{D}_k \subset \mathcal{D}_{\text{train}}$ définie par une strate sociologique ou spatiale $k \in \mathcal{K}$ (tranche d'âge, motif, catégorie socio-professionnelle, classe de distance), la part modale macroscopique estimée pour le mode $m$ sous le prompt $p$ est la moyenne des probabilités verbalisées :

$$\hat{P}_{k,m}(p) = \frac{1}{|\mathcal{D}_k|} \sum_{i \in \mathcal{D}_k} \pi(m \mid s_i; p)$$

Soit $\mathbf{P}^*_k$ le vecteur de référence empirique issu de l'enquête pour la strate $k$. La calibration de prompt se formule comme un problème d'optimisation discrète sous contraintes :

$$\min_{p \in \Pi} \mathcal{L}(p; \mathcal{D}_{\text{train}}) = \sum_{k \in \mathcal{K}} w_k \, D_k\left(\hat{\mathbf{P}}_k(p), \mathbf{P}^*_k\right) \quad \text{sous contraintes} \quad \begin{cases} \mathcal{C}_{\text{qualitative}}(p) = 1 \\ \mathcal{C}_{\text{agnostique}}(p) = 1 \end{cases}$$

où $D_k$ représente la divergence de Jensen-Shannon ($\mathrm{JSD}$) pour les variables nominales et la distance de transport optimal ($\mathrm{EMD}$) pour les variables ordinales ordonnées, pondérées par $w_k$. Les prédicats $\mathcal{C}_{\text{qualitative}}$ et $\mathcal{C}_{\text{agnostique}}$ imposent le respect des garde-fous d'admissibilité définis ci-après.

### 5.3.2 Optimisation discrète réfléchie

L'espace textuel $\Pi$ étant discret et non différentiable, l'optimisation procède par recherche réfléchie assistée par modèle (*reflective discrete optimization*), dans la lignée des approches *Reflexion* (Shinn et al., 2023) et *TextGrad* (Yuksekgonul et al., 2024).

À chaque itération $t$, le système calcule la matrice des résidus empiriques strate par strate :

$$\mathbf{R}^{(t)} = \left( \hat{\mathbf{P}}_k(p^{(t)}) - \mathbf{P}^*_k \right)_{k \in \mathcal{K}}$$

Un méta-optimiseur (LLM doté d'un budget de raisonnement dédié) analyse cette matrice d'écarts, formule une hypothèse cognitive sur le biais de raisonnement sous-jacent, et propose une mutation textuelle ciblée $p^{(t+1)}$.

Le traitement de l'élasticité à la distance illustre ce mécanisme. Lors de la campagne de référence, la part attribuée à la voiture individuelle restait stable à travers toutes les classes de distance (42,7 %, 46,6 %, 40,4 %, 42,6 %, 49,1 %), alors que l'enquête enregistre une progression de 18 % à 77 %. Corrélativement, la part de marche à pied était sous-estimée de 44,7 points sur les trajets de moins de 1 km, et surestimée de 8,5 points au-delà de 10 km. Le méta-optimiseur n'injecte pas de consigne directe sur la distance, mais introduit une règle comportementale fondée sur le coût d'engagement d'un véhicule : préparer un véhicule motorisé (déverrouillage, sortie de stationnement, manœuvres d'accès) impose une friction temporelle et cognitive incompressible, ce qui réduit sa pertinence pour les déplacements courts tout en préservant son avantage sur les longues distances.

<!-- source: docs/arch/prompt_calibration.md § 2.9, axe « echelle » et levier cout_fixe_vehicule -->

### 5.3.3 Complexité et arbitrage face aux algorithmes évolutionnaires

L'optimisation évolutionnaire classique de prompts (*EvoPrompt*, Guo et al., 2023) génère des populations de variantes évaluées par croisement et sélection stochastique. Si cette approche s'est révélée efficace sur des tâches de classification textuelle unitaire, son application à la simulation multi-agents se heurte à une barrière d'échelle computationnelle.

Dans un modèle multi-agents, la fonction d'adaptation (*fitness*) ne s'évalue pas sur un échantillon isolé, mais sur l'émergence d'une distribution macroscopique à l'échelle d'une cohorte complète d'agents. Pour une population de 10 prompts évaluée sur 10 générations auprès de 800 personas, le protocole requiert $10 \times 10 \times 800 = 80\,000$ inférences d'agents. Ce coût computationnel rend l'exploration évolutionnaire aveugle disproportionnée par rapport aux gains marginaux attendus. Le choix d'une recherche réfléchie guidée par la matrice des résidus résout ce verrou en concentrant l'exploration sur des mutations causalement justifiées.

### 5.3.4 Les quatre garde-fous d'admissibilité

Quatre contraintes méthodologiques garantissent que la calibration ne dégénère pas en mémorisation artificielle des statistiques de l'enquête :

1. Règle 1 : interdiction des seuils chiffrés ($\mathcal{C}_{\text{qualitative}}$). Le méta-optimiseur a l'interdiction d'insérer des valeurs numériques, des bornes kilométriques ou des objectifs quantitatifs (« privilégier la marche sous 1,5 km », « viser 55 % de choix automobile »). Un analyseur syntaxique automatique élimine avant évaluation tout candidat enfreignant cette règle. Le prompt ne manipule que des notions d'arbitrage qualitatif : friction d'accès, fatigue physique cumulée, exposition aux intempéries ou contraintes d'horaires stricts.
2. Règle 2 : cloisonnement strict des populations. Les personas utilisés pour piloter la calibration proviennent d'un vivier d'entraînement totalement disjoint de la cohorte scellée du chapitre 4 ($\mathcal{D}_{\text{train}} \cap \mathcal{D}_{\text{scellée}} = \emptyset$). La recherche s'appuie sur une partition de criblage rapide (~20 % des données d'entraînement) et une partition de validation pour l'arrêt précoce. L'évaluation rapportée au chapitre 6 mesure donc une performance de généralisation hors échantillon.
3. Règle 3 : mesure sur distributions verbalisées continues. Sur une cohorte de 800 personnes, un tirage stochastique discret induit une variance d'échantillonnage de $\pm 1,7$ point sur les parts modales pour un même prompt. Afin d'éliminer ce bruit, le score de calibration est calculé directement sur les vecteurs de probabilités continues verbalisés par le modèle. Cette disposition garantit qu'une mutation n'est validée que sur un gain structurel avéré.
4. Règle 4 : mémoire Tabu, attribution de crédit et compaction. Une mémoire Tabu enregistre les sémantiques de mutations déjà rejetées pour éviter les explorations redondantes. Une décomposition modulaire en blocs de raisonnement indépendants, évaluée par ablation unitaire ($N-1$) ou valeurs de Shapley, quantifie l'impact marginal de chaque directive. Une passe finale de compaction élimine les blocs dont la contribution n'atteint pas le seuil de non-infériorité statistique, bornant ainsi la longueur du prompt final.

Le méta-optimiseur est en outre contraint par le prédicat $\mathcal{C}_{\text{agnostique}}$ : interdiction de citer nommément les étiquettes sociologiques de l'enquête (catégories professionnelles, tranches d'âge ou communes cibles). Le prompt doit formuler ses heuristiques sous forme de principes universels transposables à d'autres territoires.

### 5.3.5 Statut des variantes et étanchéité de l'évaluation

Une seule variante issue de ce processus constitue le prompt expert de référence : celle dont l'optimisation a été menée sans jamais exposer le méta-optimiseur à la cohorte scellée, et dont la consigne de justification ne porte aucun *a priori* modal. Les variantes exploratoires ajustées directement sur les résidus de la cohorte scellée sont isolées méthodologiquement et publiées sous le statut de borne haute d'ajustement en échantillon, matérialisant le coût de généralisation hors échantillon.

<!-- source: ticket 080 § 3.4, révisé le 2026-09-17 — prompt_expert_05 = palier 2, promu ce jour-là ; prompt_expert_04, qui portait ce statut, a été supprimé du dépôt à la demande de l'auteur et n'est plus servable ; prompt_expert_06/07/08 = ajustés au vu de la cohorte, publiés à part -->

Seule l'instruction système distingue cette condition du prompt minimal. Le bloc de faits soumis au modèle (persona, offre d'itinéraires calculée, agenda de la journée, contexte météorologique) est produit par la même chaîne et présenté dans la même forme qu'au § 5.1, et la réponse attendue suit le même schéma JSON. Le texte de la variante de référence, seul élément qui change, est le suivant :

> *Select the optimal travel mode taking the persona into account.*
>
> *Situational trade-off principles:*
>
> - *Chain friction: Reconstruct the real door-to-door duration (access walk, waiting, in-vehicle trip, egress). If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting.*
> - *Autonomy of older people: For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps to climb, standing while waiting with no bench).*
> - *Carrying logistics: Take into account the physical constraint of loads (shopping, heavy bags, carrier bags). Carrying loads on public transport is off-putting; the trade-off leans towards direct access with no interchange (an immediate neighbourhood walk, or the boot of a private vehicle).*
> - *Working people's life time: For a working person facing a tightly scheduled day, the time taken away from personal life has critical value. Faced with public transport links that significantly increase the duration or impose multiple interchanges, the traveller prefers the efficiency and schedule control of their available vehicle.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile through these principles.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variante prompt_expert_05 (277 mots, famille « experte », audit de neutralité conforme du 2026-09-14, sha256 du texte 5f55688f9cb3ba3e1e6c6f96549a339858ac72b110d9bdc7d14651c216b53ef4) ; le schéma JSON attendu suit la consigne et est reproduit en annexe -->

Quatre principes d'arbitrage s'ajoutent aux consignes de sortie du § 5.1, que la variante reprend à l'identique hormis le renvoi aux principes dans la première. Aucun ne comporte de valeur numérique, de borne kilométrique ni de cible de part modale (règle 1), et aucun ne nomme une catégorie professionnelle, une tranche d'âge ou une commune de l'enquête (prédicat d'agnosticité) : la friction de chaîne, la marche continue à son rythme pour une personne âgée, le port de charges et la valeur du temps personnel d'un actif contraint s'énoncent comme des mécanismes transposables. L'écart avec le prompt minimal tient à ces quatre directives seules, la tâche et le format de réponse restant inchangés.

## 5.4 Les deux bouts de l'échelle : planchers et références tabulaires

L'interprétation d'un écart de distribution exige de positionner le modèle entre deux bornes méthodologiques : le niveau atteint sans connaissance comportementale et le niveau atteint par des modèles entraînés sur les réponses réelles.

Le plancher caractérise la performance de décideurs ignorant toute information comportementale et sociologique :
- Le hasard uniforme : distribution égale de la probabilité entre toutes les options calculées pour le déplacement ($1 / |\mathcal{O}_i|$).
- L'a priori empirique (zero-rule) : attribution systématique de l'ensemble de la probabilité au mode majoritaire global du territoire (la voiture individuelle).
- L'heuristique physique de durée minimale : sélection déterministe de l'itinéraire présentant le temps de trajet le plus faible sur les graphes de transport.

Le plafond correspond à la performance des quatre modèles tabulaires supervisés présentés au § 4.4 (logit multinomial, gradient boosté, forêt aléatoire, régression logistique à noyau). Ces modèles disposent des 21 variables du contrat et ont été entraînés sur 39 203 déplacements réels de l'enquête, dont l'agent n'a lu aucun enregistrement. Comme aucune méthode tabulaire ne domine simultanément sur les trois métriques (parts globales, composite L1, composite EMD–JSD), le plafond est défini par la frontière de Pareto des meilleurs scores obtenus par ces modèles sur chaque axe.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PALIER 0 : PLANCHERS STATISTIQUES & HEURISTIQUES PHYSIQUES                   │
│ • Hasard uniforme ──► zéro information.                                     │
│ • Prior empirique (zero-rule) ──► prédit toujours la voiture.               │
│ • Heuristique de durée minimale ──► min(durée OTP).                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 1 : PROMPT MINIMAL ET CIRCONSTANCIÉ (aucune ingénierie de prompt)    │
│ • Persona complet + options d'itinéraires OTP/OSM + consigne neutre.        │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 2 : PROMPT EXPERT (optimisation réfléchie sous garde-fous)           │
│ • Consignes contextuelles d'arbitrage, sans aucun seuil chiffré.            │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 3 : RÉFÉRENCES TABULAIRES AJUSTÉES SUR L'ENQUÊTE                     │
│ • Logit multinomial, LightGBM, forêt aléatoire, régression logistique       │
│   à noyau : toutes sous la contrainte de chaîne, comme les agents.         │
└─────────────────────────────────────────────────────────────────────────────┘
```

Conformément à la séparation entre protocole et résultats, les scores numériques associés aux planchers et au plafond ne sont pas présentés dans ce chapitre : ils sont consolidés au tableau comparatif du chapitre 6. Deux repères méthodologiques encadrent néanmoins la démarche : l'écart entre les planchers et le plafond couvre un ordre de grandeur (les planchers affichant des divergences sept à quatorze fois plus élevées que les modèles supervisés), et une autre cohorte de 1 000 personas de même construction déplacerait le composite d'un décideur de $\pm 1,3$ point (IC95, rééchantillonnage par grappe au niveau de la personne).

Dualité des échelles d'évaluation. Les scores composites synthétisent des distributions agrégées calculées sur une cohorte synthétique représentative. Cependant, cette cohorte ne disposant pas d'une vérité terrain individuelle déclarée, la mesure de l'exactitude désagrégée nécessite un protocole spécifique, développé au § 5.5.

<!-- repères d'exactitude sur la partition de test de l'enquête (13 045 déplacements, découpage par ménage, poids de redressement) : a priori « toujours la voiture » 57,1 %, logit multinomial 76,6 %, forêt aléatoire 77,6 %, régression logistique à noyau 78,4 %, gradient boosté 78,5 %. Sources : scripts/progedo_logit/{mode_choice_policy,klr_model,rf_mode_choice,mnl_model}_metrics.json, test.accuracy_weighted ; l'exactitude de l'a priori vaut la part observée de la voiture. Ces chiffres ne viennent PAS des scores.json de la campagne v6, qui ne portent aucune exactitude. Ils ne sont pas commensurables avec les composites : jeux différents, supports différents. -->

## 5.5 L'audit à parité de terrain : régler l'agent là où la vérité existe

L'évaluation de la politique locale de choix modal ne peut se limiter à la fidélité macro-distributionnelle sur une population synthétique : elle doit être complétée par un audit décision par décision, confronté à des choix réels vérifiables.

Ce protocole d'audit à parité de terrain mobilise la partition de test scellée de l'enquête ménages-déplacements (13 045 déplacements réels), sur laquelle les modèles tabulaires sont formellement validés. Pour chaque déplacement observé, l'offre d'itinéraires multimodaux est reconstruite par les mêmes moteurs que ceux de la simulation (plus court chemin routier et OpenTripPlanner sur les grilles horaires de référence), à partir des centroïdes des zones d'origine et de destination et de l'horaire de départ documenté.

L'ensemble des décideurs est alors soumis à cette même offre : l'agent sous prompt minimal, l'agent sous prompt expert, les quatre modèles tabulaires supervisés (renormalisés sur l'offre selon la règle 3 du contrat) et le prior empirique. Cette confrontation unitaire permet de calculer les métriques de classification désagrégées annoncées au § 4.2 : exactitude globale pondérée, entropie croisée (LogLoss), matrices de confusion multi-classes, précision et rappel par mode de transport.

Deux limites inhérentes à la reconstitution historique doivent être précisées :
1. L'origine et la destination correspondent à des centroïdes de zones fines et non à des adresses géolocalisées exactes ; l'offre calculée reflète ainsi le déplacement représentatif de la zone.
2. L'agenda effectif de la journée vécue par l'enquêté n'étant que partiellement disponible, les conditions environnementales sont tirées dans la fenêtre d'observation de l'enquête.

Cet audit évalue les modèles sur le substrat de données qui a servi à entraîner les références supervisées. L'analyse des matrices de désaccord par motif ou par classe de distance permet d'isoler les failles de raisonnement de l'agent unitaire et d'orienter les ajustements qualitatifs du prompt, complétant ainsi l'analyse macroscopique par une vérification de cohérence individuelle. Le détail méthodologique et les seuils de cet audit sont documentés au [ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md).

---

### Tickets associés à ce chapitre
- [Ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — Restructuration des chapitres 5 et 6, absorption du 4.5
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — Synthèse du benchmark multi-modèles et variabilité inter-graines
- [Ticket 004](../../../tickets/ticket_004_prompt_calibration_industrialisation.md) — Industrialisation de la calibration de prompt
- [Ticket 054](../../../tickets/ticket_054_sobriete_computationnelle_prompt_calibration.md) — Sobriété computationnelle de la calibration
- [Ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md) — Périmètre et méthode de l'audit unitaire (§ 5.5)
