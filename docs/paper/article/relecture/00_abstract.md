<!--
AAMAS_ABSTRACT_EN_v0.1_vs_v0.2.md — comparaison des deux versions du résumé AAMAS 2027.

  v0.1 : 339 mots — version de travail du 9 septembre 2026 (340 une fois la coquille
         « a prioribut » séparée en deux mots).
  v0.2 : 240 mots — réduction demandée de 30 % (mesurée : −29,2 %).

Contrainte de soumission : l'enregistrement du résumé sur OpenReview demande
100 à 300 mots en texte brut (cf. INSTRUCTIONS_SOUMISSION_AAMAS.md, § 2.2).
v0.1 dépassait la borne haute, v0.2 la respecte.

Décompte : placeholders <xx> comptés pour un mot, commandes LaTeX exclues.
Texte miroir, à tenir dans la même passe : GAMA_DAYS_ABSTRACT_EN_TEX.md (488 mots,
orienté architecture et plateforme, sans mesure individuelle).
-->

# Résumé AAMAS 2027 — v0.1 (339 mots) contre v0.2 (240 mots)

| | v0.1 | v0.2 | écart |
|---|---|---|---|
| **§1 Cadrage** | 88 mots | 67 mots | −24 % |
| **§2 Dispositif et mesures** | 116 mots | 82 mots | −29 % |
| **§3 Résultats** | 109 mots | 70 mots | −36 % |
| **§4 Portée** | 26 mots | 21 mots | −19 % |
| **Total** | **339 mots** | **240 mots** | **−29,2 %** |

Convention de décompte : chaque placeholder `$\langle \textbf{xx} \rangle$` compte pour un
mot, les commandes LaTeX (`\\`, `\,`, `\%`, `$^2$`) et les délimiteurs `\begin{abstract}` /
`\end{abstract}` n'en comptent aucun.

---

## §1 — Cadrage

| v0.1 | v0.2 |
|---|---|
| Multi-agent simulations of urban mobility traditionally rely on tabular models, discrete choice models, or supervised learning, estimated from surveys, or on explicit rule systems. In both cases, the space of representable behaviors is fixed a priori by the specification: a factor that has not been encoded as a variable or rule cannot influence any decision. Agents based on large language models (LLMs) promise to overcome this limitation; we show that they do so at the cost of a clear trade-off between statistical calibration and adaptation to exceptional situations. | Multi-agent simulations of urban mobility rely on tabular models estimated from surveys or on explicit rules. Either way the space of representable behaviours is fixed a priori: a factor encoded as neither variable nor rule cannot influence any decision. Agents based on large language models (LLMs) promise to lift it; we show they do at the price of a trade-off between calibration and adaptation to exceptional situations. |

**Ce qui a sauté.** L'énumération `discrete choice models, or supervised learning, estimated from
surveys` — « tabular models estimated from surveys » les couvre déjà, et l'article détaille les
deux références au § 2. `by the specification` et `In both cases` sont redondants avec
« fixed a priori ».

---

## §2 — Dispositif et mesures

| v0.1 | v0.2 |
|---|---|
| We evaluate LLM agents on modal choice in the Toulouse metropolitan area. A synthetic population of 1000 individuals are generated using eqasim. Alternative routes are calculated on real networks using OpenTripPlanner. Agents operate within the GAMA multi-agent platform, which subjects them to the physical constraints and uncertainties of the transportation system. Decisions are compared to the CEREMA 2023 EMC$^2$ survey at two scales: aggregated modal shares (L1 difference in percentage points) and individual decisions on a sealed test set of $\langle \textbf{nb\_trajets} \rangle$ paths (accuracy, log-loss). Two references frame the comparison with identical variables: the *a priori* empirical (majority mode, the car, $\langle \textbf{xx} \rangle$ % accuracy) as floor, and a supervised oracle (LightGBM) estimated on the survey as ceiling. | We evaluate LLM agents on mode choice in Toulouse: 1,000 synthetic individuals (eqasim), itineraries on the real networks (OpenTripPlanner), decisions taken inside GAMA, which grounds them in the transport system's physical constraints. We measure against the CEREMA 2023 EMC$^2$ survey at two scales: aggregate modal shares (L1, points) and individual choices on a sealed test set of $\langle \textbf{nb\_trajets} \rangle$ trips (accuracy, log-loss). At identical variables, the majority mode (car, $\langle \textbf{xx} \rangle$\,\%) sets the floor and a LightGBM oracle fitted on the survey the ceiling. |

**Ce qui a sauté.** Quatre phrases du dispositif fondues en une seule énumération ; `and
uncertainties of the transportation system` (les contraintes physiques suffisent, et
l'incertitude est portée par le § 3) ; `L1 difference in percentage points` → `L1, points`.

**Corrections de fond.** `A synthetic population … **are** generated` (accord) ; `modal choice`
→ `mode choice` (usage du domaine) ; `paths` → `trips` (l'unité de mesure est le déplacement).

---

## §3 — Résultats

| v0.1 | v0.2 |
|---|---|
| The LLM agent fails in statistical calibration: it exhibits major systematic biases: underestimation of walking ($\langle \textbf{xx} \rangle$ % against $\langle \textbf{xx} \rangle$ % observed) and the over-attractiveness of cycling ($\langle \textbf{xx} \rangle$ % against $\langle \textbf{xx} \rangle$ %) and its unit accuracy of $\langle \textbf{xx} \rangle$ % exceeds the a priori but the gap with the oracle remains significant ($\langle \textbf{xx} \rangle$ %). On the other hand, it provides specific added value on two regimes that no tabular amnestic model can produce: adaptation to real news events from the local press and post-incident behavioral hysteresis (major subway breakdown, bicycle fall, etc.) on a kinetic of $\langle \textbf{N} \rangle$ days, supported by a short- and medium-term memory register that revises the perception of risk. | Calibration fails: walking is underestimated ($\langle \textbf{xx} \rangle$\,\% against $\langle \textbf{xx} \rangle$\,\% observed), cycling over-attractive ($\langle \textbf{xx} \rangle$\,\% against $\langle \textbf{xx} \rangle$\,\%), and individual accuracy of $\langle \textbf{xx} \rangle$\,\% beats the prior but stays $\langle \textbf{xx} \rangle$ points below the oracle. In exchange they produce two regimes no memoryless tabular model can: adaptation to real events from the local press, and behavioural hysteresis over $\langle \textbf{N} \rangle$ days after an incident (metro breakdown, bicycle fall), carried by a memory register that revises perceived risk. |

**Ce qui a sauté.** Le double deux-points de la première phrase ; `it provides specific added
value on` → `they produce` ; `on a kinetic of N days` → `over N days` ; `short- and medium-term`
(le registre est décrit dans le corps de l'article).

**Corrections de fond.**

1. `the gap with the oracle remains significant ($\langle xx \rangle$ %)` était ambigu — écart L1
   ou accuracy ? Devenu `stays $\langle xx \rangle$ points below the oracle`, donc des points
   d'accuracy, cohérent avec la proposition qui précède.
2. `unit accuracy` est un calque de « précision unitaire » → `individual accuracy`.
3. **Question ouverte, à trancher avant de remplir les `xx`** : le biais annoncé sur le **vélo**
   ne correspond pas à ce qui est mesuré. Le run du 8 septembre 2026 donne une sur-attraction des
   **transports en commun** (26,5 % contre 12,4 % observés) et la sous-estimation de la marche
   (15,3 % contre 26,8 %).
   Source : `data/experiences/exp_gemini-35-fl_expcham5_jtir_t0_nosim_2/executions/2026-09-08_20_28_52/scores.json`
   et `scripts/data/population/cerema_values.yaml`. La formulation « cycling » a été conservée
   telle quelle ; la remplacer par « public transport » ne change pas la longueur.

---

## §4 — Portée

| v0.1 | v0.2 |
|---|---|
| We derive from this perspectives of implications for hybrid architectures, where the tabular model ensures calibration and the LLM agent handles deviations from the nominal regime. | This points to hybrid architectures, where the tabular model secures calibration and the LLM agent handles departures from the nominal regime. |

**Ce qui a sauté.** `We derive from this perspectives of implications for` (six mots pour un
« this points to »).

---

## v0.2 complète, prête à coller

```latex
\begin{abstract}
Multi-agent simulations of urban mobility rely on tabular models estimated from surveys or on explicit rules. Either way the space of representable behaviours is fixed a priori: a factor encoded as neither variable nor rule cannot influence any decision. Agents based on large language models (LLMs) promise to lift it; we show they do at the price of a trade-off between calibration and adaptation to exceptional situations.
\\\\We evaluate LLM agents on mode choice in Toulouse: 1,000 synthetic individuals (eqasim), itineraries on the real networks (OpenTripPlanner), decisions taken inside GAMA, which grounds them in the transport system's physical constraints. We measure against the CEREMA 2023 EMC$^2$ survey at two scales: aggregate modal shares (L1, points) and individual choices on a sealed test set of $\langle \textbf{nb\_trajets} \rangle$ trips (accuracy, log-loss). At identical variables, the majority mode (car, $\langle \textbf{xx} \rangle$\,\%) sets the floor and a LightGBM oracle fitted on the survey the ceiling.
\\\\Calibration fails: walking is underestimated ($\langle \textbf{xx} \rangle$\,\% against $\langle \textbf{xx} \rangle$\,\% observed), cycling over-attractive ($\langle \textbf{xx} \rangle$\,\% against $\langle \textbf{xx} \rangle$\,\%), and individual accuracy of $\langle \textbf{xx} \rangle$\,\% beats the prior but stays $\langle \textbf{xx} \rangle$ points below the oracle. In exchange they produce two regimes no memoryless tabular model can: adaptation to real events from the local press, and behavioural hysteresis over $\langle \textbf{N} \rangle$ days after an incident (metro breakdown, bicycle fall), carried by a memory register that revises perceived risk.
\\\\This points to hybrid architectures, where the tabular model secures calibration and the LLM agent handles departures from the nominal regime.
\end{abstract}
```

## v0.1 complète, pour archive

```latex
\begin{abstract}
Multi-agent simulations of urban mobility traditionally rely on tabular models, discrete choice models, or supervised learning, estimated from surveys, or on explicit rule systems. In both cases, the space of representable behaviors is fixed a priori by the specification: a factor that has not been encoded as a variable or rule cannot influence any decision. Agents based on large language models (LLMs) promise to overcome this limitation; we show that they do so at the cost of a clear trade-off between statistical calibration and adaptation to exceptional situations.
\\\\We evaluate LLM agents on modal choice in the Toulouse metropolitan area. A synthetic population of 1000 individuals are generated using eqasim. Alternative routes are calculated on real networks using OpenTripPlanner. Agents operate within the GAMA multi-agent platform, which subjects them to the physical constraints and uncertainties of the transportation system. Decisions are compared to the CEREMA 2023 EMC$^2$ survey at two scales: aggregated modal shares (L1 difference in percentage points) and individual decisions on a sealed test set of $\langle \textbf{nb\_trajets} \rangle$ paths (accuracy, log-loss). Two references frame the comparison with identical variables: the \textit{a priori} empirical (majority mode, the car, $\langle \textbf{xx} \rangle$ \% accuracy) as floor, and a supervised oracle (LightGBM) estimated on the survey as ceiling.
\\\\The LLM agent fails in statistical calibration: it exhibits major systematic biases: underestimation of walking ($\langle \textbf{xx} \rangle$ \% against $\langle \textbf{xx} \rangle$ \% observed) and the over-attractiveness of cycling ($\langle \textbf{xx} \rangle$ \% against $\langle \textbf{xx} \rangle$ \%) and its unit accuracy of $\langle \textbf{xx} \rangle$ \% exceeds the a prioribut the gap with the oracle remains significant ($\langle \textbf{xx} \rangle$ \%). On the other hand, it provides specific added value on two regimes that no tabular amnestic model can produce: adaptation to real news events from the local press and post-incident behavioral hysteresis (major subway breakdown, bicycle fall, etc.) on a kinetic of $\langle \textbf{N} \rangle$ days, supported by a short- and medium-term memory register that revises the perception of risk.
\\\\We derive from this perspectives of implications for hybrid architectures, where the tabular model ensures calibration and the LLM agent handles deviations from the nominal regime.
\end{abstract}
```

---

## v0.3 (11 septembre 2026) — réorientation sur les décisions de l'état de l'art

**Point de départ.** Une version de 340 mots apportée par l'auteur le 10 septembre 2026, proche de la `v0.1` : elle annonçait « we show that they do so at the cost of a clear trade-off », nommait LightGBM comme seul plafond, et promettait `accuracy, log-loss`.

**Six changements, tous adossés à une décision déjà prise :**

1. **La contribution est le contrat, non la mesure.** GTA (Lämmer, Colley & Ebel, 2026) confronte déjà une répartition modale d'agents LLM à l'enquête nationale allemande. Le résumé dit maintenant « under a contract that gives every model the same information », et les trois règles y tiennent en quelques mots : parité (« the same 21 variables »), lecture homologue (« read against the tabular models' renormalised probabilities »), renormalisation (« on the modes actually offered »).
2. **Deux références tabulaires.** Le logit multinomial entre ; le mot *ceiling* sort, Martín-Baos et al. (2023) montrant que les arbres perdent leur avantage sur les parts modales agrégées. Le logit reste à calculer (point 4.12).
3. **Les deux usages en ouverture**, à la place du verdict annoncé : substitut statistique contre système adaptatif.
4. **H0 comme hypothèse pré-enregistrée**, dans les mots du chapitre 1, et non « the LLM agent fails in statistical calibration ».
5. **Le prompt calibré nommé pour ce qu'il est** — réécrit à la main vers les parts publiées — donc un instrument, seule position tenable face à CityReal (Bougie, Ye & Watanabe, 2026).
6. **Correction factuelle**, point 4.13 : la réponse n'est plus lue « comme décision retenue », la décision en simulation étant un tirage dans la masse.

**Retiré de la version de l'auteur :** `accuracy, log-loss` (métrique non définie par le protocole) ; « bicycle fall, etc. » (seule la panne de la ligne A est dans C3) ; « short- and medium-term memory register » (C3 ne définit qu'un tampon à court terme décroissant) ; « a kinetic of N days » (cinq jours, fixé) ; plancher et plafond isolés (remplacés par les quatre paliers) ; les modes nommés (voir point 3 ci-dessus).

**Décompte.** 241 mots au décompte de soumission, 242 au découpage naïf, soit **−29,1 %** sur 340. Dans la borne de 100 à 300 mots.
