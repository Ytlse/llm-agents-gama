# Journal des résultats d'expériences

Tout résultat mesuré et tout jeu de référence gelé **susceptible d'être cité dans l'article**
est consigné ici, au fil de l'eau, avec **le chemin de sa source** pour que le chiffre puisse
être revérifié sans reconstituer la session, et **la date et l'heure de fin** de l'expérience.

Ce fichier n'interprète rien et ne conclut rien : il enregistre. La lecture des résultats vit
dans le ticket qui les a demandés, et leur passage dans l'article passe par le verrou.

**Convention.** Tous les chemins cités sont **relatifs à la racine du dépôt**, pas à ce
dossier, et toutes les commandes se lancent depuis la racine. Le composite est `emd_jsd` du
`scores.json`, formule `v1_reference`, référentiel EMC² 2023. Les heures sont locales (CEST) ; les fichiers du dépôt, eux, horodatent en UTC —
l'écart de deux heures est normal et n'indique pas deux mesures. Le nom du dossier d'exécution
est l'heure de **début** en UTC, l'heure notée ici est celle de **fin**, lue dans `etat.json`.

---

## 2026-09-25 16:00 — Presse a09 V2, relecture : les deux bras divergent dès le premier soir, par les souvenirs de gemini-3.5

**Source :** les deux mêmes bras que l'entrée de 15:14 ci-dessous, traité
`experiments/archive/2026-09-25_13_06`, témoin `experiments/archive/2026-09-25_14_09` (fin du
témoin 15:14, `etat.json`). Lu : `moves.csv` et `llm_exchanges.jsonl` des deux bras. Décisions
LLM appariées sur `(personne, activité, date)` : 132, dont 91 avant la lecture et 41 à partir
d'elle ; les 19 paires dont un trajet est un retour forcé (« Un seul itinéraire disponible ») sont écartées.

**Rejouer :**
`python3 scripts/analysis/figure_derive_bras.py experiments/archive/2026-09-25_13_06 experiments/archive/2026-09-25_14_09 docs/traces/2026-09-25_15-51_a09_v2_derive_bras/a09_v2_derive_bras.html --evenement 2026-03-26 --suivre 286923@12:40`

| Mesure | Valeur |
|---|---|
| souvenirs STM du lundi 16 envoyés avec un prompt identique dans les deux bras | 8 sur 12 appariés |
| dont réponse identique (gemini-3.5-flash-lite, température 0) | **0 sur 8** |
| prompts de décision identiques dans les deux bras (gemini-3.1-flash-lite, température 0) | 5/5 le 16, 2/10 le 17, **0 à partir du 18** |
| dont réponse identique | **7 sur 7** |
| décisions à plus de 20 points d'écart (variation totale), 16-20 mars | 1 sur 57 (2 %) |
| idem, 23-25 mars (trois derniers jours avant la lecture) | 4 sur 34 (12 %) |
| idem, 26-31 mars (à partir de la lecture) | 8 sur 41 (20 %) |
| Fisher unilatéral, à partir de la lecture contre toute la période d'avant | p = 0,017 |
| Fisher unilatéral, à partir de la lecture contre les trois derniers jours d'avant | **p = 0,28** |
| écart moyen par période (variation totale, points) | 7,1 · 10,6 · 13,6 |
| mode choisi identique dans les deux bras | 88/91 avant, 35/41 après |
| raisonnements du traité citant tempête, vent, rafales ou parcs (filtre à mots entiers) | 3 sur 41 ; témoin 0 (ses deux « park » sont « parking ») |
| trajets en marche ou vélo du foyer à partir de la lecture | 21 au traité, 21 au témoin |

**Constats de relecture.**
- Les réglages sont les mêmes dans les deux bras (`llm_params.temperature: 0` pour les décisions
  et les souvenirs, `llm_agent.py` via `settings.agent.llm_params`) ; le cache est désactivé
  (`cache: enabled: false`), ce qui désactive aussi la mémoïsation exacte des réflexions du
  ticket 012 (`llm_agent.py:630-644`).
- Créneau 286923 (garçon, 9 ans) « home » à 12:40 : modes différents dès le mer. 18 (marche au
  traité, voiture au témoin) ; vélo au traité et marche au témoin le mer. 25, veille de la lecture
  (P(vélo) 45 % contre 20 %). Aucun échange du 25 ne porte l'article (0 sur 9 lots de décision).
- Météo servie le jeudi 26 dans les deux bras : « 3°C, Clear/Sunny […] 0.2 mm over the day » ;
  aucune variable de vent. L'article annonce une vigilance jaune et des rafales au-delà de 80 km/h.
- L'article porte sa date d'origine (« this Thursday 16 July ») ; la simulation est au jeudi 26 mars.
- Les jours de service suivants, la ligne servie reste au présent : le mardi 31, le lecteur lit
  « This morning I read in the paper: « […] this Thursday evening » », et 286923 lit le lundi 30
  « My parents decided this morning: « […] closing all the parks and gardens starting at 6 p.m.
  today » » (`llm/evenements/injection.py:100` et `:111`). Un raisonnement du lundi 30 cite encore
  « storm warnings » (286923, 14:21).
- Les titres du bloc mémoire sont en français dans un prompt anglais (« Mes habitudes », « Ce que
  je sais », « Ce qui a changé récemment », « le matin : à vélo, 9 fois sur 10 »),
  `llm/noyau.py:442-445`.

**Figure :** `docs/traces/2026-09-25_15-51_a09_v2_derive_bras/a09_v2_derive_bras.html` (et `.png`),
script `scripts/analysis/figure_derive_bras.py`.

---

## 2026-09-25 15:14 — Presse a09 V2 (vent d'autan), foyer 133048, deux bras : l'article et le relais atteignent 40 décisions sur 42, l'écart aux témoins reste dans le bruit

**Source :** bras traité `experiments/archive/2026-09-25_13_06` (13:06 → 14:09, 151 trajets),
bras témoin `experiments/archive/2026-09-25_14_09` (14:09 → 15:14, 151 trajets), recopiés dans
`experiments/runs/exp_mem_presse_a09_vent_autan_gem31flite_population_4_foy_15j_foyer_2_{treated,control}/`.
Définition : `data/experiences_memoire/exp_mem_presse_a09_vent_autan_gem31flite_population_4_foy_15j_foyer_2/`
(état `terminee`). Même configuration que l'entrée du 00:08 ci-dessous, plus
`evenement_relais: gemini-3.1-flash-lite` ; code `main` à `10f3ad3` (ticket 111, retenue de
l'horloge `0058908`, récit du foyer servi le soir seulement). Réglages vérifiés 8/8 sur les deux
bras. Journal : `experiments/enchainement_nuit_20260925_1306.log`.

**Conditions.** Un premier lancement à 13:02 a été arrêté par le lanceur au bout de 3 min : deux
contrôleurs démarrés dans la même minute partageaient `experiments/archive/2026-09-25_13_02`, dont
l'identité ne portait pas les réglages de l'expérience. Ce répertoire est sans valeur. Relance
propre à 13:06. Aucune décision de repli, aucun trajet perdu (286921 : 57 trajets dans chaque bras,
contre 52 au traité du premier run), 7 erreurs HTTP 503 rattrapées au nouvel essai, 1 réflexion STM
en retard au réveil du 26 mars.

**L'exposition et le relais.** Lecteur 286920, jour 11 (jeudi 26 mars, 00:00 simulé), gravité 0,30,
valence négative, modes `['walking', 'cycling']`. Relais : un appel (6,3 s), trois messages, tous
les membres informés — il ne reste aucun co-résident non informé. Les trois messages parlent de la
fermeture des parcs à 18 h ; aucun ne parle de vélo ni de mode. Jugés par les informés : 286921
0,30 (`walking`, `cycling`), 286922 0,50 (aucun mode), 286923 0,30 (aucun mode). Le run finit le
mardi 31 mars, quatrième des cinq jours de service garantis.

| Mesure | Valeur |
|---|---|
| décisions LLM du traité à partir de la lecture portant l'article ou le message du foyer | **40 sur 42** (les 2 autres sans prompt journalisé) |
| dont décisions calculées avant l'injection (jours 10 et 11) | 10 |
| contrôle « lecture avant décision » (`scripts/debug/run_report.py`) | 4 agents ✅, 0 🔴 |
| messages écrits en mémoire longue chez les informés | 3 sur 3 |
| tableau des quatre voies, informés (38 décisions) | changements 38 · connaissances ~10 · rappel ~2 |
| tableau des quatre voies, lecteur (4 décisions) | changements 4 · rappel 0 |
| raisonnements du traité qui citent la tempête ou les parcs | ~~4~~ **3** sur 41 décisions appariées (corrigé le 2026-09-25 16:00 : le quatrième, 286921 le 26 mars 13:38, disait « parking » — voir l'entrée de 16:00 ci-dessus) |
| choix du lecteur | voiture dans toutes ses décisions, dans les deux bras |

**Écart aux témoins** (distance de variation totale entre distributions déclarées, 132 décisions
appariées) : avant la lecture, médiane 5 points, 9e décile 20 ; à partir de la lecture, médiane 5,
9e décile 45, et 8 décisions sur 41 au-dessus de 20. Modes à partir de la lecture, traité contre
témoin : 286921 voiture 8/9, marche 7/7, TC 2/1 ; 286923 vélo 11/7, marche 3/7 ; 286920 et 286922
identiques. Avant la lecture, 286923 diffère déjà (vélo 13 contre 11).

- 286923, vendredi 27 mars 17:36 : P(vélo) 60 % au traité, 0 % au témoin. Le raisonnement du traité
  cite la tempête (« Given the storm warning and high winds, the child prefers the speed and
  efficiency of cycling or walking home directly »). Au premier run, même trajet : 0 % au traité,
  60 % au témoin.
- 286921, lundi 30 mars 17:10 : écart de 100 points (TC contre voiture) ; au traité, la voiture
  ne figurait pas parmi les options (chaîne des véhicules).
- Aucun concept n'a traversé le foyer dans les deux bras (0 sur 26 examens au traité, règles R1 et
  R2), comme au premier run.

**Fausse alarme connue.** `temoin_souvenir.jsonl` rend « PERDU » pour 286921 le 25 mars : le
contrôle a tourné avec une heure simulée antérieure à l'écriture (26 mars 00:00) ; le message est
dans sa mémoire longue (`long_term_memory/user_metadata/shard_89/286921.json`).

**Figure :** `docs/traces/2026-09-25_15-30_a09_v2_presse_foyer/a09_v2_presse_foyer.html` (et `.png`),
script `figure_a09_v2.py` dans le même dossier, non installé dans le dépôt à cette date.

---

## 2026-09-25 00:08 — Presse a09 (vent d'autan), foyer 133048, deux bras : l'article traverse le foyer, aucune décision du jour ne le lit

**Source :** bras traité `experiments/archive/2026-09-24_17_50` (segment repris 22:01 → 23:05,
146 trajets), bras témoin `experiments/archive/2026-09-24_23_06` (23:06 → 00:08, 151 trajets),
recopiés dans `experiments/runs/exp_mem_presse_a09_vent_autan_gem31flite_population_4_foy_15j_foyer_{treated,control}/`.
Définition : `data/experiences_memoire/archive/exp_mem_presse_a09_vent_autan_gem31flite_population_4_foy_15j_foyer/`
(état `echec`, archivée le 2026-09-25 ; remplacée par `…_foyer_2`).
Population `population_4_foyer_133048` (4 agents), 15 jours calendaires depuis le 2026-03-16,
gemini-3.1-flash-lite (décision) et gemini-3.5-flash-lite (réflexion STM), `prompt_expert_05`,
graines 42. `identite_run.json` identique entre les bras hors empreinte d'événement.

**Conditions.** Le bras traité a échoué trois fois au jour 1 (17:50, 18:08, 18:30 : timeouts
`itinary_multi_agent`, trois replis consécutifs, hibernation), puis a été repris à 22:01 depuis
t0 ; aucune décision de repli ne subsiste dans son `moves.csv`. Le traité perd **5 trajets**
de 286921 entre le 24 au soir et le 26 au matin : la décision de son départ de 17:01 le 24 est
servie vers 18:20 simulé, l'horloge ayant avancé pendant l'attente du modèle.

**L'exposition.** Lecteur 286920 (homme, 40 ans, actif) au jour 11 (jeudi 26 mars, 00:00
simulé), gravité jugée 0,30, `notable`, valence négative, modes `['walking']` (grille 095 :
`[notable, genant]`, `[walking, cycling]`).

| Mesure | Valeur |
|---|---|
| décisions LLM du jour 11 dont le prompt porte l'article | **0 sur 11** |
| décision 05:57 du lecteur le jour 11 | calculée le 25 à 07:00 simulé, 17 h avant l'injection |
| décisions ultérieures portant l'article (jours 12 à 16) | 6 : 286923 ×3 (27 mars), 286920 ×2 (30, 31), 286921 ×1 (30) |
| co-résidents ayant reçu le récit en réflexion STM | 3 sur 3, le 26 entre 07:30 et 18:15 simulé |
| co-résidents l'ayant écrit en mémoire longue | 2 sur 3 (286921 à 13:45, 286923 à 15:15) |
| raisonnements de décision citant la tempête | 0 |
| choix du lecteur | voiture 24/24 dans les deux bras |

**Plancher de bruit** (distance de variation totale entre distributions déclarées, 126 décisions
appariées) : avant la lecture, médiane 10 points, 9e décile 26,5, et 13 choix sur 86 déjà
différents entre les bras. Des six décisions portant l'article, une dépasse le 9e décile
(286923, 27 mars 17:36, P(vélo) 0 % contre 60 %) ; son raisonnement invoque l'habitude.

**Figure :** script proposé, non installé à cette date (analyse de session du 2026-09-25).

---

## 2026-09-24 14:55 — Ticket 103 (Phase 5) : dispersion inter-graines de Jev sur prompt minimal (graines 123 et 789)

**Source :**
- Graine 123 : `data/experiences/exp_jev-1130_promin02_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go123_gt123_gc123_nosim/executions/2026-09-24_12_03_50` (12:03:50 → 12:05:32 UTC, soit 14:03 → 14:05 CEST, 3 299 trajets, 3 151 décisions).
- Graine 789 : `data/experiences/exp_jev-1130_promin02_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go789_gt789_gc789_nosim/executions/2026-09-24_12_53_52` (12:53:52 → 12:55:21 UTC, soit 14:53 → 14:55 CEST, 3 299 trajets, 3 153 décisions).
- Graine 42 (référence historique c1) : `data/experiences/exp_jev-1130_promin02_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_nosim/executions/2026-09-21_06_27_05` (3 158 décisions).

Décideur typé `typesafe:jev-1.13.0`, prompt `prompt_minimal_02`, cohorte c1 de 1 000 personas (jeu 2026-03-16, 3 299 trajets dont 3 161 exploitables). Chaque exécution aligne `graine_ordre`, `graine_tirage` et `calendrier.graine` sur la même valeur (123 ou 789).

**Conditions d'exécution :** Zéro erreur (`erreurs.jsonl` absent), **zéro repli uniforme**, couverture > 99,7 % dans les deux cas. Exécution purement locale / Docker, sans appel réseau ni passerelle.

### Résultats mesurés

| Graine | Composite `emd_jsd` | `emd_jsd` hors choix unique | `l1` | Décisions libres | Couverture |
|---|---|---|---|---|---|
| **Graine 42** (ref) | **13,748** | 19,836 | 134,52 | 3 158 / 3 161 | 99,9 % |
| **Graine 123** | **13,450** | 18,862 | 131,64 | 3 151 / 3 161 | 99,7 % |
| **Graine 789** | **13,337** | 18,909 | 131,07 | 3 153 / 3 161 | 99,7 % |

- **Étendue inter-graines (*inter-seed range*) :** **0,411 point** (de 13,337 à 13,748).
- **Parts modales agrégées (graine 123 / graine 789 / graine 42) :**
  - Marche : 23,61 % / 23,56 % / 23,39 %
  - Vélo : 6,95 % / 6,88 % / 6,94 %
  - Voiture privée : 37,96 % / 39,26 % / 38,40 %
  - Transports collectifs : 31,23 % / 30,00 % / 30,95 %
  - Train : 0,25 % / 0,29 % / 0,32 %
  - Deux-roues motorisé : 0,00 % / 0,00 % / 0,00 %

### Chapitres et sous-chapitres de l'article enrichis

1. **Tableau 1 (Table 1 — Comparative performance of the 15 decision-makers) :**
   - Renseigne la colonne *Inter-seed range* pour la ligne `Typed classifier (jev-1.13.0) + minimal prompt` avec la valeur mesurée exacte : **0,41 point**.
   - Cette étendue est plus étroite que celle de Gemini 3.5 Flash (0,56 point) et reste très inférieure à la résolution de la cohorte ($\pm 1,3$ point).
2. **Section 4.4 (Planchers, références, décideurs) :**
   - Établit empiriquement la stabilité de la chaîne typée `jev-1.13.0` face aux permutations de tirage et d'ordre d'évaluation (ticket 096 / ticket 103), confirmant l'absence d'effets d'ordre notables.
3. **Section 5.1 (Quinze décideurs sur une échelle) :**
   - Démontre que la dispersion inter-graines du classifieur à sortie typée ($\Delta = 0,41$) est négligeable devant le gain apporté par le réglage expert du prompt ($\Delta \approx 10,1$ points entre minimal 13,75 et expert 3,65 sur c1).
4. **Annexe D (§ D.2, Tableau D.1, Tableau D.2) :**
   - Fournit les points de contrôle et les graines pour la réplication stricte des distributions du décideur typé sans stochasticité cachée.

---

## 2026-09-24 06:41 — Campagne c3 (v7), deux bras : le choc atteint la mémoire et ne change rien

**Source :** bras traité `experiments/archive/2026-09-24_00_15` (00:15 → 03:28, 277 trajets),
bras témoin `experiments/archive/2026-09-24_03_28` (03:28 → 06:41, 299 trajets), recopiés dans
`experiments/runs/e_c3_attribution_861500_v7/`. Persona 861500, événement `c3_panne_reseau`,
injection au jour simulé 12 (`2026-03-27T19:23:11`, gravité 0,75). Les deux bras couvrent
2026-03-16 → 2026-04-25.

**Conditions LLM.** Traité : 20 saturations, **zéro repli**. Témoin : 13 saturations et **un
repli** — `[ALARME] Vecteur de probabilités inexploitable (somme nulle) — repli sur une
distribution uniforme sur 5 options`, le 2026-09-24 à 05:14, une décision sur 299. Le témoin
porte aussi une `[ALARME] Arrivée perdue` (person=861500, attendue le 20 mars 19:50, dépassée
de 2 j 23 h).

### Le témoin du ticket 106 : verdict « retrouvé », et l'identifiant est désormais nommé

    2026-03-27 | c3_panne_reseau | retrouvé | 4/9 | lighting, announcement, appointment, fourth

Première trace portant `evenement_id` renseigné (correction du 2026-09-24). Le bras témoin
n'écrit aucun `temoin_souvenir.jsonl` : sans injection, le contrôle ne se déclenche pas — c'est
le contrôle négatif du témoin lui-même, et il passe.

### Le résultat : aucune différence entre les deux bras

Part des transports collectifs **décidée** — le TC était dans les modes proposés ET
`Méthode de sélection == LLM` :

| Fenêtre | traité | témoin |
|---|---|---|
| avant le choc | 10/46 — 21,7 % | 12/56 — 21,4 % |
| j+0 → j+6 | 13/34 — 38 % | 12/38 — 32 % |
| j+7 → j+13 | 10/38 — 26 % | 8/34 — 24 % |
| j+14 → fin | 26/83 — 31 % | 25/90 — 28 % |

Les lignes de base concordent à 0,3 point, ce qui valide l'appariement des graines. Après le
choc, l'écart entre les deux bras ne dépasse jamais 6 points et va dans le sens **inverse** de
l'évitement attendu : une panne de métro ne détourne pas cet agent des transports collectifs.

### Pourquoi, et c'est le vrai résultat : le souvenir est écrit puis jamais rappelé

|  | c3 (cette nuit) | c6 (2026-09-23) |
|---|---|---|
| entrées de mémoire longue portant le choc | **1** sur 353 | **31** sur 307 |
| dont concepts | 0 | 2 |
| **rappels cumulés** de ces entrées | **1** | **52** |
| effet sur le mode visé | aucun | effondrement pendant 20 jours |

L'entrée unique du run c3 n'est pourtant pas un résidu : importance 0,75, récit complet, et une
intention explicite — *« For future planning, I need to keep in mind the unreliability of the
metro when scheduling important appointments. »* Elle a été rappelée **une fois**, le lendemain
matin à 05:42, puis plus jamais en quatre semaines.

**Ce que cela dit du témoin du ticket 106 :** « retrouvé » répond à *le texte a-t-il survécu à
la consolidation ?*, et pas à *l'agent décide-t-il avec ?*. Le témoin reste nécessaire ; il
n'est pas suffisant.

⚠ **CORRECTION DU 2026-09-24, même journée.** Le paragraphe ci-dessus concluait d'abord qu'un
souvenir rappelé une fois équivalait à un souvenir perdu. La mesure suivante l'a démenti, et
elle est consignée ici plutôt que retirée, parce que le raisonnement qu'elle invalide était
plausible. Le compte des rappels de mémoire longue **ne mesure pas** ce qui est servi au
modèle : le run `2026-09-19_18_09` totalise **zéro rappel** et fait pourtant chuter la voiture
décidée de 95 % à 48 %. La mesure qui tient est celle du § 7.2.1 de l'article — la présence du
souvenir dans le **prompt de décision**, tous canaux confondus. En ancrant sur les mots du
texte injecté qui n'apparaissent dans aucun prompt d'avant le choc (calibration automatique,
sans liste d'exclusion), ce compte rend 75 prompts porteurs sur le run du § 7.2.1 : le chiffre
publié.

Sur ce compte, le run c3 de cette nuit sert le souvenir dans **85 de ses 155 décisions
postérieures au choc (55 %), et jusqu'au dernier jour simulé**. Le souvenir n'est donc ni
perdu, ni dormant, ni absent du contexte : **il est devant le modèle une décision sur deux, et
le modèle continue de prendre le métro.** Le résultat est comportemental, pas instrumental.

### Ticket 108 confirmé sur un second run, avec une cause plus générale

`evenement.yaml` déclare **deux** jours d'injection (12 et 13), `evenements.jsonl` n'en porte
**qu'une**. Comme la veille, rien ne le signale. Mais la cause diffère : ici le choc n'a pas
supprimé la condition de sa propre répétition — l'agent continue d'utiliser les transports
collectifs après le 27 mars. Le jour 13 (2026-03-28) est simplement un jour où il n'a pris que
la voiture. **Une injection conditionnée à un mode et posée sur un jour fixe manque chaque fois
que l'agent n'emprunte pas ce mode ce jour-là**, choc ou pas.

---

## 2026-09-23 23:42 — Run v6 : le témoin du ticket 106 exercé en vrai, et une courbe de rupture-retour sur 27 jours

**Source :** `experiments/archive/2026-09-23_20_35`, recopié dans
`experiments/runs/e_c3_attribution_861500_v6/861500_treated`. Lancé à 20:35, terminé à 23:42 —
**186 minutes**, 33 jours simulés (16 mars → 26 avril 2026), 178 trajets.

⚠ **Deux écarts à retenir avant de citer quoi que ce soit d'ici.** La commande a tourné sans
`--evenement` : l'identifiant d'expérience dit `c3` mais **l'événement injecté est
`c6_voiture_suspecte`** (panne moteur sur voie rapide, `evenement.yaml` du run fait foi). Et
seul le bras `treated` a été joué (`--branch treated`) : **il n'y a pas de bras contrôle**,
donc aucune attribution n'est établie — ce qui suit est une trajectoire observée, pas un écart
mesuré contre un témoin.

**Conditions LLM.** 19 erreurs sur 186 minutes, dont **13 `HTTP 503 « high demand »`** — contre
11 en 6 minutes lors du v5. **Zéro repli** : le garde-fou du ticket 105 n'a pas eu à se
déclencher, et aucune décision n'a été servie par défaut.

### Le témoin du souvenir injecté (ticket 106) a parlé pour la première fois en conditions réelles

Une injection, au jour simulé 15 (`2026-03-30T05:32:55`, gravité 0.8427). Le contrôle post-
consolidation la retrouve :

| Agent | Jour simulé | Verdict | Mots retrouvés |
|:--|:--|:--|:--|
| `861500` | 2026-03-30 | ✅ retrouvé | engine, stalled, expressway, middle, lane, lorry, behind, hard, metres, bumper, shoulder, waited, roadside, assistance, restart |

**15 mots distinctifs sur 23**, pour un seuil de 2. La marge est celle qu'annonçait la
calibration sur les 13 runs archivés (3–81 mots du côté gardé, 0–1 du côté perdu), pas un
passage de justesse. `temoin_souvenir.jsonl` : 1 ligne, 0 perte.

À noter : l'`evenement.yaml` du run déclare **deux** jours d'injection (15 et 16) et **un seul**
a été consigné dans `evenements.jsonl`. La seconde injection ne s'est pas produite — l'exposition
est restreinte au mode `car`, que l'agent n'a plus choisi après le choc. Le témoin ne peut donc
contrôler que ce qui est injecté.

### Part modale : la part brute et la part décidée ne disent pas la même chose

La part brute mélange les choix et la mécanique de chaîne : `sortie_bloquee` passe de 8 trajets
avant le choc à 39 après. Une fois parti sans la voiture, l'agent ne peut plus la reprendre de
la journée — la baisse brute compte cette propagation comme si c'était une décision.

| | part brute (tous trajets) | part **décidée** (voiture offerte **et** choix LLM) |
|---|---|---|
| Avant le choc | 72,2 % voiture (57/79) | **97,2 % (35/36)** |
| Après le choc | 23,2 % voiture (23/99) | **33,3 % (15/45)** |

### La trajectoire jour par jour, sur les décisions libres

| Fenêtre | Voiture / décisions libres | |
|---|---|---|
| j−14 → j−2 | 34 / 36 | 94,4 % |
| j+0 | 1 / 4 | 25,0 % |
| j+2 → j+19 | **0 / 28** | 0,0 % |
| j+21 → j+27 | 14 / 15 | 93,3 % |

Vingt jours à zéro, puis un retour net au niveau d'avant. Le choc reste cité dans le
raisonnement de presque chaque décision jusqu'à j+19 (7/7 à j+10, 9/9 à j+14, 7/7 à j+16), puis
se dilue (1/5 à j+22, 0/4 à j+24).

**Le retour ne vient pas d'un oubli.** À j+21, j+22 et j+23, le raisonnement rappelle la panne
*et* choisit quand même la voiture — verbatim de j+22 :

> « Although Capucine has recently relied on public transport due to a car breakdown, her
> historical preference and the significant time savings of the car (11 minutes vs 46+ minutes)
> make it her primary choice for efficiency […] »

Le souvenir est encore là et ne gouverne plus. Le point de bascule tombe exactement entre j+19
et j+21 ; les paramètres de durée du run sont `plancher_changement_jours: 2.0`,
`plafond_changement_jours: 50.0`, `fenetre_changements_jours: 14`, `changements_max: 3`
(`identite_run.json`). Le lien entre ce j+21 et ces valeurs **n'est pas établi** ici.

---

## 2026-09-23 19:41 — Campagne c3 (v5) : arrêtée par le garde-fou, au premier jour

**Source :** `experiments/archive/2026-09-23_19_32`, `app.log`, `llm_errors.jsonl`,
`en_attente_quota.json`. Lancée à 19:32, arrêtée à 19:41 — **neuf minutes**.

Relance du bras traité `861500 / c3_panne_reseau` après le ticket 105 (arrêt sur replis) et le
ticket 106 (témoin du souvenir injecté), dans l'hypothèse d'une saturation retombée. Elle ne
l'était pas — elle avait empiré.

| | cet après-midi (v4) | ce soir (v5) |
|---|---|---|
| `HTTP 503 « high demand »` | 54 sur la journée, pic à 1,5/min | **11 en 6 minutes, soit ~2/min** |
| Clés touchées | `google_gemini31_key1/2` | les deux, en alternance |
| Décisions servies par le modèle | 118 avant l'arrêt | **1 sur 4** |

**Le garde-fou du ticket 105 a fonctionné dès sa première rencontre réelle.** Trois replis
consécutifs — 16 mars 05:00, 07:48, puis le troisième — chacun sur un `Timeout expiré` de 120 s,
`genre_erreur=aucun` (une saturation ne renvoie aucun genre d'erreur, c'est tout l'objet du
ticket). Le contrôleur s'est arrêté au **jour 1** plutôt que de remplir la mesure de choix par
défaut, et le marqueur dit pourquoi :

    {"motif": "replis_consecutifs", "resume_at": null,
     "replis_consecutifs": 3, "person_id": "861500", "jour_simule": 1}

`resume_at: null` et non la chaîne `"None"` : une saturation n'annonce aucune heure de
réouverture, et le marqueur ne doit pas faire croire à une date.

**Ce que ça valide, et ce que ça ne dit pas.** Le v4 avait laissé quatre décisions par défaut
entrer dans la fenêtre de mesure sur 2 h 22, découvertes à la main. Le v5 s'est arrêté en neuf
minutes avec zéro décision par défaut dans une fenêtre de mesure — il n'y a pas eu de fenêtre de
mesure. En revanche **le témoin du ticket 106 n'a pas été exercé** : l'injection est au jour 12,
le run est mort au jour 1. Il reste vérifié sur archive seulement.

**Décision.** Pas de relance ce soir. La règle tient : on attend le renouvellement plutôt que de
servir une décision qui n'en est pas une. Les deux garde-fous sont en place, la prochaine fenêtre
de disponibilité sera exploitable sans surveillance manuelle.

---

## 2026-09-23 — Le choc n'a pas survécu à la consolidation (bras v4) — défaut NON DÉTERMINISTE

**Ce que c'est.** Constat fait en préparant la reprise du bras v4 au dernier jour propre. Le
souvenir du choc c3, jugé `grave (0.75)` et RETENU à 0,75 en mémoire **courte**, **n'est jamais
arrivé en mémoire longue**. Le bras est donc nul indépendamment des replis : à partir du jour 13,
l'agent ne se souvient de rien.

**La preuve, dans l'ordre.**

| Instant simulé | Ce qui se passe |
|---|---|
| 27 mars 13:30 | consolidation — absorbe les entrées jusqu'à 13:29 |
| **27 mars 14:02** | **le choc entre en mémoire courte**, jugé 0,75, RETENU 0,75 |
| 27 mars 19:30 | consolidation suivante — couvre 13:30 → 19:30, **donc le choc** |

Ce qu'elle a écrit en mémoire longue : *« Today went very smoothly overall, with all my trips
adhering closely to schedule. »* — importances 0,10 et 0,15. Les trois seules entrées à 0,75 de la
journée datent de **12:38**, avant le choc, et portent sur un bus manqué.

Recherche exhaustive dans les 123 documents de mémoire longue du run : `metro`, `lighting`,
`announcement`, `carriage`, `fourth time` → **0 occurrence**. Le point de reprise `jour_017` ne le
porte pas davantage.

**La cause mécanique.** Le texte de l'événement est **joint** à l'observation d'arrivée, jamais
substitué — choix délibéré, commenté dans `simulation_controller.py` : « l'agent doit garder ce que
la simulation a mesuré, et y ajouter ce qu'il a vécu ». L'entrée de mémoire porte donc les deux
ensemble :

> `[ ARRIVAL ] Arrived for home; Actual duration: 44 minutes; On time.` … `[ INCIDENT ] The metro
> stopped between two stations … I missed the appointment … arrived 28 minutes after the time I
> had planned.`

La partie mesurée dit **« On time »** (`arrive_at` 1774620168 contre `expected_arrive_at`
1774620367 : arrivé 199 s **en avance**), le récit dit 28 minutes de retard. `retard_injecte_s`
(1680 s) ne va qu'au journal des arrivées, il ne touche pas l'arrivée elle-même. La consolidation a
tranché la contradiction en faveur du chiffre.

**⚠ C'EST STOCHASTIQUE, ET MOINS RARE QU'ANNONCÉ D'ABORD.** Mesuré sur **tous** les runs
archivés portant une injection, en cherchant dans la mémoire longue les mots distinctifs du texte
injecté lui-même. Deux runs (`2026-09-17_07_18`, `2026-09-18_19_27`) n'ont **aucune** consolidation
après l'injection — le run s'était arrêté avant — et sortent du champ : il n'y a rien à y chercher.

| | runs observables | choc gardé | choc perdu |
|---|---|---|---|
| `c6_voiture_suspect` | 8 | 8 | 0 |
| `c3_panne_reseau` | 4 | 2 | **2 — `09_31` et le v4** |
| `a13_punaises_metro` | 1 | 1 | 0 |
| **total** | **13** | **11** | **2 (15 %)** |

Sur le seul événement c3, **un run sur deux perd le choc**.

La séparation entre les deux groupes est **franche** : les runs qui gardent le souvenir retrouvent
de 3 à 81 mots distinctifs, ceux qui le perdent en retrouvent 0 et 1. Aucun run ne se situe au
voisinage du seuil.

Deux runs du même jour, même configuration, même texte : `11_10` le garde (neuf mots sur neuf :
« lighting », « announcement », « restarted », « carriage », « packed »…), `13_54` le perd (un
seul, « missed »). La perte est donc **stochastique** — ce qui est plus dangereux qu'un défaut
constant : elle est invisible et peut frapper un bras et pas l'autre, c'est-à-dire fabriquer ou
effacer l'effet qu'on mesure.

⚠ **Correction de DEUX lectures antérieures de cette même session.** Le run `2026-09-23_09_31` a
été compté successivement comme perdu, puis comme gardé, puis de nouveau comme **perdu** — ce
dernier verdict étant le bon, et le seul appuyé sur une liste d'exclusion calibrée. La deuxième
lecture le donnait gardé sur la foi de deux mots, « lighting » et « missed » ; ils venaient de
phrases sans rapport avec la panne. Ses six réflexions disent *« Today went entirely according to
schedule with no complications »*. Le taux de perte annoncé à 7 % (1 sur 15) est donc en réalité
de **15 % (2 sur 13)**.

**Deux pièges de vocabulaire, tous deux silencieux, à retenir pour toute mesure de ce type.**
`incident` correspondait à *« without any unexpected incidents »* — qui dit exactement le
contraire de ce qu'on cherche. `between` était le seul mot que le v4 retrouvait, dans *« a short
walk between errands »*, et suffisait à le faire passer pour un run sain. La règle d'admission
dans la liste d'exclusion : *ce mot apparaîtrait-il dans la réflexion d'un jour ordinaire ?*

**Conséquence immédiate.** La reprise du bras v4 depuis `jour_017` est **abandonnée** : elle
repartirait d'un agent qui ne se souvient pas du choc.

**L'importance ne peut pas servir de témoin — mesuré, piste fermée.** L'idée naturelle serait de
vérifier que la consolidation qui suit l'injection produit une entrée d'importance comparable à
l'importance retenue. Elle ne marche pas : sur les 13 runs où les deux chiffres sont lisibles,
**7 ont une importance maximale de mémoire longue INFÉRIEURE à l'importance retenue**, et surtout
`11_10` — qui garde parfaitement le choc — plafonne à **0,10**, comme `13_54` qui le perd (0,15).
L'importance attribuée en mémoire courte ne se propage pas en mémoire longue. Tout témoin devra
donc porter sur le **contenu**, pas sur le score.

**Livré le 2026-09-23 — ticket 106.** Le contrôle existe : après chaque consolidation qui
consomme une entrée injectée, les mots distinctifs du texte sont cherchés dans ce qui vient
d'être écrit en mémoire longue. En dessous de deux mots retrouvés, `[ALARME] [temoin]` nomme
l'agent et les mots, et `make report` rend les deux verdicts.

Le témoin **alarme et n'arrête pas**, contrairement à celui des replis livré le même jour : il est
heuristique là où l'autre constate un fait, et une paraphrase légitime produirait une fausse
alarme qui tuerait un bon run. `temoin_souvenir.jsonl` porte les deux verdicts pour que le taux de
fausses alarmes s'observe sur des runs réels.

**Reste à trancher par l'auteur.** La calibration ci-dessus sépare les 13 runs sans cas limite, et
le défaut touche 1 run sur 7 — 1 sur 2 pour c3. Les deux poussent vers l'arrêt plutôt que la
simple alarme. À dire quand quelques runs auront tourné sous le témoin.

**Tranché le 2026-09-23 : l'arrivée NE portera PAS le retard injecté.** Le récit reste joint à
l'observation sans la modifier, comme le code le fait déjà. La contradiction interne à l'entrée
(`On time.` d'un côté, « arrived 28 minutes after » de l'autre) est donc assumée.

---

## 2026-09-23 — Campagne c3 (v4) : arrêtée sur pénurie LLM amont, bras inexploitable

**Ce que c'est.** Reprise complète de la campagne d'attribution (bras traité puis témoin) après
les correctifs du matin. **Arrêtée sur incident au jour 19**, pas sur fin de poste : une pénurie
de service chez Google a dégradé les décisions au-delà du tolérable. **Aucune mesure
d'attribution n'en sort.**

| | |
|---|---|
| Répertoire | `experiments/archive/2026-09-23_13_54` |
| Lancée / arrêtée | 13:54 → 16:16 (CEST), au 3 avril 19:03 simulées |
| Avancement | jour 19 sur 42, 118 déplacements, bras traité seul (témoin jamais lancé) |
| Replis avant le choc | **0 / 48** — ligne de base propre |
| Replis dans la fenêtre de mesure | **4 / 39 = 10,3 %** |
| Choc | jour 12, 27 mars, jugé `grave (0.75)`, RETENU 0.75, `ecart_au_fait` −0,1167 |
| Alarmes de jugement tardif | 0 |
| Retards aberrants (> 10 000 s) | 0 |

**Ce qui a marché.** Les trois correctifs livrés le matin tiennent : le choc est jugé et retenu
à la valeur déclarée, aucun jugement n'arrive après consolidation, aucun départ reporté n'est
compté comme retard subi. Le frein de rétro-pression ne ralentit plus un run à un agent.

**Pourquoi l'arrêt : saturation amont, PAS épuisement de quota.** Les replis
`LLM Error (Default index)` sont des décisions prises sur l'index par défaut, pas par le modèle.
Ils sont apparus **uniquement après le choc**, à partir de +5,8 jours, et le taux est monté de
0 % à 10,3 % en une quarantaine de minutes.

Cause mesurée sur le worker, réponse de Google mot pour mot : `HTTP 503 — "This model is
currently experiencing high demand. Spikes in demand are usually temporary."`, statut
`UNAVAILABLE`. **54 occurrences sur la journée**, dont la montée est nette :

| tranche | 503 « high demand » |
|---|---|
| 14h10 → 15h30 | 1 à 4 par 10 min |
| 15h40 | 10 |
| 15h50 | 11 |
| 16h00 | 15 |
| 16h10 | 9 |

**Aucune erreur de quota le 23/09** : `RESOURCE_EXHAUSTED` = 0, `Quota exceeded` = 0 (les 4 du
journal datent des 21 et 22/09). Le facteur limitant est la capacité de Google, pas le budget.

Mécanisme du repli : les deux clés `gemini31` en refroidissement simultané, le drain atteint son
plafond de 30 s, GAMA avance et la décision se rabat sur `itineraries[0]`.

**Pourquoi c'est disqualifiant.** La fenêtre de mesure est exactement celle où l'on cherche
l'effet du souvenir sur le choix modal. Une décision sur dix n'y est plus celle de l'agent.

**Reprise : ce bras ne se reprend pas, il se refait.** `CONT=1` reprendrait dans le même
répertoire **en ajoutant** aux fichiers existants : les 4 replis resteraient dans `moves.csv`, et
ils sont groupés entre +5,8 et +7,8 jours après le choc, là où l'effet cherché est le plus fort.
Les diluer dans 42 jours ne les enlève pas. La campagne repart donc de zéro sous un nouvel
identifiant (`v5`). `CONT=1` ne vaut que pour du débogage, pas pour une mesure.

**Budget : non contraignant.** Les compteurs `rpd:*` de Redis sont informatifs, ne pilotent
aucun routage, et ne voient que cette application — d'autres applications consomment le même
quota. Le seul signal qui fasse foi est l'erreur renvoyée par Google, et elle n'a pas signalé de
quota le 23/09. Aucune fenêtre d'attente à respecter côté budget : la relance se décide sur le
taux de 503, pas sur l'heure de réinitialisation.

**Témoin avant relance.** Il n'existe pas de sonde passive : à T+10 min de la relance,
`docker logs --since 10m llm-agents-gama-worker-1 2>&1 | grep -c "high demand"` — sous 5 par
tranche de 10 min, c'est le régime normal du run ; au-dessus de 10, c'est celui qui a produit les
replis, et il faut arrêter.

⚠ **Compter `"high demand"`, pas `503`** : la chaîne `503` apparaît dans les horodatages et les
identifiants de tâche Celery, et un `grep -c 503` surévalue le compte d'environ un facteur 7.

**Garde-fou manquant, à ouvrir.** Le ticket 077 (axe 3) arrête déjà le run plutôt que de laisser
l'index 0 passer pour une décision du modèle — mais seulement sur `genre_erreur ==
"quota_journalier"`. La saturation amont traverse ce garde-fou. Tant qu'il n'est pas étendu, une
reprise `CONT=1` après un épisode de 503 repart d'un agent qui porte déjà des déplacements qu'il
n'a pas choisis.

**Déséquilibre de clés, à traiter.** 204 requêtes sur `google_gemini31_key1` contre 26 sur
`key2` à poids égal : la clé chargée atteint sa limite RPM et attire les 503. Non traité pendant
la mesure, à ouvrir en ticket.

---

## 2026-09-23 — Campagne c3 (v3) : les deux correctifs tiennent en run réel

**Ce que c'est.** Reprise de la campagne d'attribution après correction des deux défauts
bloquants du matin. **Arrêtée volontairement au jour 12**, le soir du choc, pour cause de fin de
poste — pas sur incident. Le bras est incomplet : **aucune mesure d'attribution n'en sort**.
Ce qui en sort est la vérification des deux correctifs en conditions réelles.

| | |
|---|---|
| Répertoire | `experiments/runs/e_c3_attribution_861500_v3/861500_treated` |
| Lancée / arrêtée | 11:10 → 12:09 (CEST), au 27 mars 21:45 simulées |
| Avancement | jour 12 sur 42, 67 déplacements |
| Replis `LLM Error (Default index)` | **0** |
| Replis sur distribution uniforme (`somme nulle`) | **0** |
| Quota | 3.1 : 126/1000 · 3.5 : 141/1000 (départ 73 et 81) |

### Le jugement est retenu, et non plus perdu

    jour 12 | 2026-03-27 | jugé grave (0.75) | RETENU 0.75 | fait mesuré 0.8667
    ecart_au_fait -0.1167 | alarmes de jugement tardif : 0

`importance_retenue` vaut la gravité **jugée par l'agent**, là où la tentative du matin avait
retenu 0,8667, le fait mesuré. L'écart au fait est **exactement celui du 2026-09-22** (−0,1167)
sur le même texte : le verdict `grave` est reproductible d'un run à l'autre.

Le seuil d'alarme D7 de 0,30 compte désormais **trois** points de mesure : +0,22 (c6, banc),
−0,1167 (c3, run du 22), −0,1167 (c3, run du 23).

### Plus aucun retard fabriqué par le calendrier

    retards aberrants (> 10 000 s) : 0

Le run du matin en portait un au **19 mars** (23,6 h, bouclage J+1) et un au **23 mars** (71,6 h,
report de week-end). Les deux dates sont passées, le compteur est à zéro : la ligne de base ne
porte plus de souvenir « grave » fabriqué par un report.

### Ce qu'il reste à faire

Rejouer les deux bras d'un bout à l'autre. ~3 h par bras, quota très large (le bras a consommé
53 requêtes 3.1 et 60 requêtes 3.5 pour douze jours).

    python3 scripts/experiment/run_sequential_cohort.py \
      --evenement c3_panne_reseau --personas 861500 --branch both \
      --experiment-id e_c3_attribution_861500_v4 --arret-sur-extinction

**Source :** `experiments/runs/e_c3_attribution_861500_v3/861500_treated/evenements.jsonl`,
`…/app.log`, `…/moves.csv`

---

## 2026-09-23 — Bras traité c3 (v2) : ARRÊTÉ AU JOUR 12, deux défauts bloquants

**Ce que c'est.** Première tentative de campagne d'attribution sous `jugement: a_l_injection`.
Arrêtée au jour 12 sur 42, le jour même du choc. **Aucune mesure n'en est citable.** Le quota
consommé est négligeable (3.1 : 73/1000, 3.5 : 81/1000).

| | |
|---|---|
| Répertoire | `experiments/current` au 2026-09-23 10:26 (CEST) |
| Persona | 861500, population d'un agent |
| Avancement | jour 12 sur 42, 79 déplacements |
| Replis `LLM Error (Default index)` | **0** |
| Routage | `itinary`+`ltm` ← gemini-3.1 · `stm`+`enquête` ← gemini-3.5 |

### Défaut 1 — le jugement perd une course qu'il perdra toujours

Le jugement a rendu **`grave` (0,75)**, le même verdict qu'hier et que le garde-fou. Il est
arrivé **cinq secondes après** que l'entrée eut été consommée, et l'événement a été qualifié sur
le fait mesuré, **0,8667**.

    10:24:08  [gravite] CHOC pour 861500 à 27 March 2026, 14:02 : I_det=0.87
    10:24:09  [reflexion-stm] agent=861500 concepts=2          ← consolidation, 1 s après
    10:24:14  « c3_panne_reseau » jugé : grave (0.75)          ← 5 s trop tard

**Ce n'est pas une latence de modèle** : le jugement a été PLUS RAPIDE qu'hier (6 s contre 14 s).
La consolidation n'a pas eu lieu le soir mais à 14h02 simulées, parce que
`STM_REFLECTION_MIN_ENTRIES = 10` déclenche la réflexion **au seuil d'entrées** — et l'entrée du
choc est celle qui a fait franchir le seuil. Elle a déclenché la consolidation qui l'a consommée.

Structurel, donc : **chaque fois que l'entrée injectée est la dixième, le jugement perd.** Hier
il a gagné parce que l'injection est tombée à 19h23 sur un tampon moins rempli. Le tirage se joue
run par run sur le nombre de trajets qui précèdent le choc.

⚠ Le texte de l'alarme dit « la consolidation du soir » : il se trompe aussi sur le moment.

**Source :** `experiments/current/app.log` lignes 6067-6080, `…/evenements.jsonl`

### Défaut 2 — un départ reporté du week-end compte comme un retard subi

    23 March 2026, 19:27 : I_det=0.70 (arrival, retard 257807 s)   ← 2,98 jours
    19 March 2026, 19:27 : I_det=0.70 (arrival, retard  85007 s)   ← 23,6 heures

Sous `NO_WEEKEND_DEPARTURES`, un départ de samedi est reporté au lundi ; le retard d'arrivée est
alors mesuré contre le plan d'origine, et l'agent enregistre un souvenir de gravité **0,70**.

Pour une expérience d'attribution, c'est disqualifiant : **la ligne de base porte des souvenirs
« graves » indiscernables du choc**, dont la gravité déclarée est 0,75.

Le défaut **préexiste au correctif du frein** : le run du 2026-09-22 en porte un (60 485 s).

**Source :** `experiments/current/app.log`, lignes `[gravite] CHOC … (arrival, retard …)`

### Défaut 3 — une décision servie sur distribution uniforme

Une occurrence de `[ALARME] Vecteur de probabilités inexploitable (somme nulle) — repli sur une
distribution uniforme sur 5 option(s)`. Elle **n'apparaît pas** dans la colonne
`Méthode de sélection` de `moves.csv`, qui reste à zéro repli : le taux de repli mesuré par cette
colonne ne voit pas cette dégradation-là.

---

## 2026-09-23 — Relecture de la campagne c6 citée au § 7.2 de l'article long

**Ce que c'est.** Pas une mesure neuve : la relecture de l'archive dont le § 7.2 tire ses
chiffres. Trois écarts entre ce que l'archive contient et ce que le dépôt produirait
aujourd'hui.

| | |
|---|---|
| Archive | `experiments/archive/2026-09-18_19_27` |
| Choc | `c6_voiture_suspecte`, agent unique |
| Injections enregistrées | **4, toutes au jour 15** (30 mars 2026) |
| Jour 16 déclaré | **jamais appliqué** — absent de `chocs.jsonl` |
| Retard injecté | `retard_injecte_s: 1800`, soit **30 minutes** |
| Gravité servie | **0,700** |
| Déplacements ce jour-là | 2, tous deux en voiture |

**Ce que le dépôt produirait aujourd'hui.** `c6_voiture_suspecte.yaml` déclare `retard_min: 45`
et le régime de saturation est passé de `palier` à `asymptote` le 2026-09-21 :

| retard déclaré | gravité aujourd'hui | durée servie |
|---|---|---|
| 20 min | 0,3333 | 8,82 j |
| 30 min | 0,5000 | 11,76 j |
| 45 min | 0,6427 | 14,27 j |
| *(0,700 — valeur du run)* | *0,700* | *15,29 j* |

Durées dérivées de `force = min(2,8 × (1 + 6 I), 30)` puis `durée = force × 1,0498`. La formule
est recoupée sur deux valeurs connues d'ailleurs : elle rend 15,29 j pour 0,700 (chiffre du
§ 7.2.1) et 16,17 j pour 0,750 (chiffre du garde-fou du 2026-09-22).

**Source :** `experiments/archive/2026-09-18_19_27/chocs.jsonl`, `…/moves.csv`
**Vérifier :** `python3 -c "import json;[print(json.loads(l)['jour_run'], json.loads(l)['retard_injecte_s'], json.loads(l)['gravite']) for l in open('experiments/archive/2026-09-18_19_27/chocs.jsonl')]"`

> ⚠ **Le § 7.2 n'est pas faux, il est devenu irreproductible.** « 30 puis 20 minutes, soit 0,700
> puis 0,533 » décrit exactement ce qui a été injecté. Un relecteur qui rejoue le cas depuis le
> dépôt d'aujourd'hui obtient d'autres chiffres et conclura à une erreur. Points à corriger
> listés dans [`../NOTE_AU_REDACTEUR.md`](../NOTE_AU_REDACTEUR.md).

---

## 2026-09-23 — Le frein de contre-pression ne s'applique plus sous la capacité de la passerelle

**Ce que c'est.** Un seuil `sans_frein` égal à la concurrence du worker (8). En deçà, toutes les
requêtes sont en vol simultanément et la pile ne grossit pas : il n'y a rien à freiner. Le
calcul relatif à la population donnait le frein maximal à un run d'un agent.

| en attente / population | avant | après |
|---|---|---|
| 1 / 1 | 30,00 s | **0,00 s** |
| 6 / 20 | 4,93 s | **0,00 s** |
| 8 / 1000 | 0,00 s | 0,00 s |
| 9 / 1000 | 0,03 s | 0,03 s |
| 300 / 1000 | 4,93 s | 4,93 s |
| 500 / 1000 | 10,61 s | 10,61 s |
| 900 / 1000 | 25,61 s | 25,61 s |

Les trois derniers régimes sont figés dans `test_backpressure.py::TestSeuilSansFrein` : si l'un
bouge, le correctif a débordé de son objet.

**Effet mesuré sur un run d'un agent :** **12 min** par jour simulé le 2026-09-22, **4,7 min**
le 2026-09-23. Ce qui reste est du temps de simulateur — 96 synchronisations par jour simulé,
dont le journal signale certaines à 5,2 s — et non de l'attente de modèle.

**Source :** `services/llm-agents/backpressure.py`, `handle/application.py:1424`
**Vérifier :** `docker compose -f infra/docker-compose.yml --project-directory . exec -T controller python -c "from backpressure import compute_backpressure_interval as f; print(f(1,1,1.5,30.0,sans_frein=8), f(300,1000,1.5,30.0,sans_frein=8))"`

---

## 2026-09-23 — Le jour 13 de c3 ne s'applique jamais

`c3_panne_reseau` déclare les jours 12 et 13. Le jour 12 tombe le **vendredi 27 mars 2026**, le
jour 13 est donc un **samedi**, et le dépôt tourne sous `NO_WEEKEND_DEPARTURES` : aucun départ,
aucun trajet en transports collectifs, la déclaration ne s'arme pas. **Une application sur deux
déclarées, dans tous les runs c3 passés et à venir.**

La déclaration n'est pas corrigée mais commentée : la retirer du seul fichier canonique
casserait l'invariant du ticket 100 (`test_100_lot1_migration.py`, `sorted(a.jours) ==
sorted(b.jours)`) qui exige que la migration déclare les mêmes jours que l'original du ticket
079 ; la retirer des deux réécrirait l'original que cet invariant protège.

**Source :** `services/llm-agents/config/evenements/c3_panne_reseau.yaml`, en tête du bloc `jours:`

---

## 2026-09-22 — Run de mise au point c3 : NON PUBLIABLE, conservé pour deux constats

**Ce que c'est.** Premier bras traité de la campagne d'attribution c3. **Aucune mesure n'en est
citable** : sa ligne de base porte 46,9 % de décisions de repli.

| | |
|---|---|
| Archive | `experiments/archive/2026-09-22_16_55` |
| Trace | `docs/traces/campagne_c3_mise_au_point/` |
| Persona | 861500 (Capucine, 58 ans), population d'un agent |
| Horizon | 42 jours déclarés, coupé au jour 40 par l'arrêt sur extinction |
| Replis **avant** le choc | **15 / 32 décisions réelles — 46,9 %** |
| Replis **après** le choc | 2 / 150 — 1,3 % |

Le marqueur de repli est la colonne `Méthode de sélection` de `moves.csv`, valeur
`LLM Error (Default index)`. Les 65 lignes `Un seul itinéraire disponible` ne sont pas des
replis et sont exclues du dénominateur.

**Deux constats qui tiennent malgré tout, et sont à confirmer sur la campagne propre :**

1. **L'agent juge `grave` (0,75) dans un vrai run.** Première fois hors appel direct sur banc,
   et c'est le verdict que les quatre personas du garde-fou avaient rendu à l'unanimité.
   `ecart_au_fait` = −0,1167, sous le seuil d'alarme D7 de 0,30.
2. **Le souvenir a vécu 21,42 jours, non les 16,17 que sa gravité seule prévoit.** La force est
   passée de 15,40 à 20,40 : cinq rappels, cinq jours de plus. La durée de vie n'est pas
   fonction de la seule gravité — l'usage la prolonge.

> ⚠ **Le journal d'échanges de ce run est pollué.** `llm_exchanges.jsonl` porte 370 requêtes
> servant **868 agents distincts**, alors que `population_1.json` n'en contient qu'un. Elles
> viennent d'un autre producteur écrivant dans le même fichier. `moves.csv` et
> `decisions_rejeu.jsonl`, eux, sont filtrés sur 861500 et indemnes — les taux de repli
> ci-dessus en sont tirés. **Ne rien déduire de `llm_exchanges.jsonl` pour ce run.**

**Source :** `experiments/archive/2026-09-22_16_55/moves.csv`, `…/evenements.jsonl`

---

## 2026-09-22 — Jeu gelé de la seconde cohorte (c2)

**Ce que c'est.** Le substrat hors échantillon du ticket 103 : aucun prompt n'y a été réglé,
tout ce qui s'y mesure est donc out-of-sample pour les deux modèles à la fois. Aucun persona
commun avec la cohorte c1.

| | |
|---|---|
| Jeu | `population_1000_AAMAS_v6_c2_20260316_EN_c` |
| Clos le | 2026-09-22 18:05 (CEST) |
| Empreinte | `3d286db12ace…` |
| Population | `population_1000_AAMAS_v6_c2`, scellée, `8c53141572ad…` |
| Jour simulé | 2026-03-16, heure de référence `depart_programme` |
| Couverture | 3 163 / 3 296 déplacements (100 %), 875 / 894 personnes mobiles |
| Inexploitables | 133, tous `origine_egale_destination`, exclus des attendus |
| Dépendances | inchangées (`verifier-jeu`) |

**Source :** `data/jeux/population_1000_AAMAS_v6_c2_20260316_EN_c/MANIFEST.yaml`
**Vérifier :** `docker compose -f infra/docker-compose.yml --project-directory . exec -T controller python -m experiences verifier-jeu --nom population_1000_AAMAS_v6_c2_20260316_EN_c`

> ⚠ **Ne pas comparer un score c2 à une bande c1.** Les deux cohortes sont disjointes et leurs
> échelles diffèrent (voir l'entrée suivante : la bande tabulaire c2 est plus basse d'environ un
> point que celle de c1).

---

## 2026-09-22 — Ticket 103, phase 3 : Gemini sur c2 (partielle)

**Un bras sur deux est rendu.** `gemini-3.5-flash-lite` sous `prompt_expert_05`, la consigne
déjà hors échantillon sur c1, est mesurée sur c2. Le second bras, sous `prompt_expert_32`, est
**interrompu à 476 décisions sur 3 163** et reste à finir.

| Bras | Composite EMD–JSD | Hors choix unique | L1 | Décidés | Fin (CEST) | Exécution |
|---|---:|---:|---:|---:|---|---|
| `gemini-3.5-fl` × `prompt_expert_05` | 4,7627 | 6,7454 | 52,687 | 3159/3163 | 2026-09-22 21:56:43 | `2026-09-22_17_49_56` |
| `gemini-3.5-fl` × `prompt_expert_32` | — | — | — | 476/3163 | interrompue | `2026-09-22_19_56_53` |

**Source :** `data/experiences/exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_t0_nosim/executions/2026-09-22_17_49_56/scores.json`
Durée 7 605 s (2 h 07), 668 décisions à itinéraire unique.

**Lecture, à la bande de sa cohorte et à rien d'autre.** Les composites bruts des deux cohortes
se ressemblent pour Gemini (4,857 sur c1, 4,763 sur c2) mais les bandes tabulaires ont bougé
d'un point entre les deux : c'est l'écart au haut de bande qui se compare, pas le composite.

| Bras | c1 : écart au haut de bande (4,09) | c2 : écart au haut de bande (3,71) |
|---|---:|---:|
| `jev-1.13.0` × `prompt_expert_32` | **dans la bande** | +0,93 |
| `gemini-3.5-fl` × `prompt_expert_05` | +0,77 | +1,05 |

Les deux décideurs perdent du terrain hors échantillon. Jev en perd davantage, ce qui est
cohérent avec le soupçon qui a ouvert le ticket : sa consigne avait été réglée sur la cohorte
qui la notait. Mais **Q2 reste sans réponse** tant que `prompt_expert_32` n'a pas été servi à
Gemini : sans cette ligne, on ne sait pas si l'avantage de la consigne tient au texte ou au
couple texte-modèle, et c'est exactement ce que le ticket voulait établir.

### Incident — le conteneur a été recréé pendant la mesure

À 22:11:52 (CEST) le service `controller` a été **recréé par un autre travail que celui-ci**
(aucune campagne n'était déclarée). Trois conséquences, toutes constatées :

1. l'exécution `2026-09-22_19_56_53` est passée à `interrompue` — « processus 1291 disparu
   (clé google_key2) » — à 476 décisions. Elle est **reprenable**, 497 décisions archivées ;
2. la simulation GAMA qu'une autre session faisait tourner a perdu son WebSocket et se
   reconnecte ;
3. les quatre paquets posés à la main pour Jev ont disparu avec l'ancien conteneur, comme
   annoncé dans l'entrée de la phase 2. `typesafe_sdk` n'est plus importable. Les phases Jev
   étant rendues, rien n'est perdu — mais **tout bras Jev relancé maintenant échouera** tant
   que l'image n'est pas reconstruite ou les paquets reposés.

**Quota au moment d'écrire :** `google_gemini35_key1` épuisée (511/500), `key2` à 374/500. Il
reste environ 126 requêtes pour un bras qui en demande environ 340 : la reprise avancera puis
se mettra en attente jusqu'au renouvellement quotidien. Conforme à la règle du dépôt — on
attend le renouvellement, on ne dégrade rien pour finir plus vite.

---

## 2026-09-22 — Figure des résultats du ticket 103

Deux panneaux, tous les chiffres lus dans les `scores.json` du dépôt, aucun écrit à la main.
À gauche, les deux cohortes côte à côte avec leur bande tabulaire : elles ne se superposent pas,
ce qui est la raison pour laquelle un score c2 ne se lit que contre la bande c2. À droite,
l'écart de chaque graine à la moyenne de son bras, contre la résolution de cohorte de ±1,3 point.

**Figure :** `docs/traces/2026-09-22_ticket103/ticket103_hors_echantillon.png` (et `.svg`)
**Régénérer :** `services/llm-agents/.venv/bin/python scripts/analysis/plot_ticket103_hors_echantillon.py --sortie docs/traces/2026-09-22_ticket103`

Un bras non encore mesuré est omis sans faire échouer le tracé : la figure se régénère entre
deux phases. Dans l'état, les deux bras Gemini sur c2 manquent, la phase 3 étant en cours.

> ⚠ La résolution de ±1,3 point est une incertitude **autour d'une valeur**, pas un intervalle
> partant de zéro. Une première version de la figure la traçait en absolu, ce qui faisait lire
> « ce bras est hors de la bande » — un contresens. Le panneau droit est donc centré sur la
> moyenne de chaque bras.

**Cette figure ne touche pas à celles de l'article.** `docs/paper/article/` est sous verrou.

---

## 2026-09-22 — Ticket 103, phase 4 : trois graines pour Jev, sur c1

**Ce que c'est.** Les deux consignes de Jev rejouées sur la cohorte c1 aux graines 123 et 789,
la graine 42 étant celle déjà publiée. Une graine vaut ici pour les trois : `graine_ordre`,
`graine_tirage` et `calendrier.graine` à la même valeur, convention des rejeux existants.

| Bras | Graine 42 | Graine 123 | Graine 789 | Étendue |
|---|---:|---:|---:|---:|
| `jev-1.13.0` × `prompt_expert_32` | 3,6470 | 3,7014 | 3,6926 | **0,0543** |
| `jev-1.13.0` × `prompt_expert_05` | 4,1399 | 4,1759 | 3,9395 | 0,2364 |
| `gemini-3.5-flash-lite` × `prompt_expert_05` *(acquis)* | 4,8571 | 4,6457 | 4,2993 | 0,5578 |

Composite EMD–JSD. Les deux premières lignes sont mesurées ici, la troisième était déjà au dépôt.

| Exécution | Fin (CEST) | Décidés |
|---|---|---:|
| `proexp32` graine 123 — `2026-09-22_17_40_01` | 2026-09-22 19:41:54 | 3152/3161 |
| `proexp32` graine 789 — `2026-09-22_17_42_01` | 2026-09-22 19:44:11 | 3154/3161 |
| `proexp05` graine 123 — `2026-09-22_17_44_16` | 2026-09-22 19:46:27 | 3154/3161 |
| `proexp05` graine 789 — `2026-09-22_17_46_33` | 2026-09-22 19:48:30 | 3154/3161 |

**Sources :** `data/experiences/exp_jev-1130_{proexp32,proexp05}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go{123,789}_gt…_gc…_nosim/executions/<exécution>/scores.json`

**Ce que cela établit.** L'écart entre les deux consignes de Jev garde **le même signe sur les
trois graines** : expert 32 devant expert 05 de 0,493, 0,474 puis 0,246 point. Le critère Q3 du
ticket est donc satisfait pour cette paire. Les trois étendues restent très en deçà de la
résolution de cohorte de ±1,3 point.

**Ce que cela n'établit pas.** Que Jev soit ou non déterministe. La graine ne change pas que le
modèle : elle change l'ordre des décisions — et la contrainte de chaîne des véhicules fait que
l'ordre compte — ainsi que le tirage dans la distribution rendue. Un décideur parfaitement
déterministe produirait lui aussi trois scores différents sous ce protocole. La question laissée
ouverte par le ticket 096 reste ouverte ; elle demanderait deux exécutions à graine identique.

---

## 2026-09-22 — Ticket 103, phase 2 : Jev hors échantillon sur c2

**Ce que c'est.** Les trois consignes servies au classifieur à sortie typée `jev-1.13.0` sur la
cohorte c2, graine 42, mêmes réglages que la phase 1. `prompt_expert_32` est le résultat pivot :
c'est la consigne réglée **sur c1**, servie ici à une cohorte qui n'a jamais servi à la régler.

| Consigne | Composite EMD–JSD | Hors choix unique | L1 | Décidés | Fin (CEST) | Exécution |
|---|---:|---:|---:|---:|---|---|
| `prompt_expert_32` | **4,6394** | 7,6741 | 45,204 | 3159/3163 | 2026-09-22 19:34:10 | `2026-09-22_17_31_54` |
| `prompt_expert_05` | 5,2511 | 7,9753 | 50,533 | 3159/3163 | 2026-09-22 19:36:39 | `2026-09-22_17_34_38` |
| `prompt_minimal_02` | 13,5813 | 19,2820 | 124,452 | 3159/3163 | 2026-09-22 19:38:56 | `2026-09-22_17_36_45` |

**Sources :** `data/experiences/exp_jev-1130_{proexp32,proexp05,promin02}_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_nosim/executions/<exécution>/scores.json`

**Ce que ces trois chiffres disent, et rien de plus.** Le classement des consignes tient hors
échantillon : expert 32 devant expert 05 devant le prompt minimal, dans le même ordre que sur c1.
Rapporté à la bande tabulaire de c2, [2,53 ; 3,71], le bras pivot est **0,93 point au-dessus du
haut de bande**. Le seuil que le ticket 103 avait fixé **avant la mesure** est de 1,3 point,
ce qui place l'issue dans son **scénario 2** : Jev ne rentre pas dans la bande hors échantillon,
mais reste sous le seuil.

> ⚠ **Rien n'est tranché à ce stade.** La question Q1 demande aussi les différences appariées de
> Jev à chacune des quatre références tabulaires, qui ne sont pas calculées. La question Q2
> exige le bras Gemini sous `prompt_expert_32` (phase 3), qui n'est pas joué. Aucune phrase de
> l'article ne se réécrit sur ces trois lignes seules.

**Pour mémoire, les mêmes bras sur c1** (en échantillon) : 3,6470 · 4,1399 · 13,7480. L'écart
d'échelle entre les deux cohortes interdit de les soustraire ; ils se lisent chacun contre sa
propre bande.

**[ALARME] relevée au scorage, attendue et non bloquante :** le composite de chaque bras dépend
des décisions à itinéraire unique (674 sur 3 159 pour expert 32, soit 21,3 % du périmètre), et
passe de 4,64 à 7,67 quand on les retire. La colonne « hors choix unique » est donnée pour cette
raison et doit accompagner toute citation du composite.

### Incident d'exécution — dépendances absentes du conteneur

Les trois premiers lancements (17:21 UTC) se sont arrêtés en quelques secondes : le décideur
`typesafe` importe `typesafe_sdk`, déclaré dans `services/llm-agents/requirements.txt` depuis le
2026-09-21 mais **absent de l'image du conteneur**, construite le 2026-09-18. Reconstruire
l'image aurait recréé le `controller` et tué la simulation qu'une autre session faisait tourner.
Les trois paquets manquants ont donc été posés dans le conteneur vivant, à leur version de
l'hôte et **sans toucher aux dépendances déjà présentes** (`pip install --no-deps`) :
`typesafe-sdk==0.7.0`, `httpx2==2.13.0`, `httpcore2==2.13.0`, `truststore==0.10.4`.

> ⚠ **Ces paquets disparaîtront à la prochaine recréation du conteneur.** La correction durable
> est une reconstruction de l'image, qui n'a pas été faite ici. Tant qu'elle ne l'est pas, tout
> bras Jev lancé après un `docker compose up --force-recreate` échouera de la même façon.

Les trois exécutions interrompues (`2026-09-22_17_21_16`, `_17_21_25`, `_17_21_33`) portent un
journal non régénérable et **leur scoring est refusé** : elles ne sont pas exploitables et sont
remplacées par les exécutions du tableau ci-dessus. Elles restent sur le disque, marquées
obsolètes par le registre.

---

## 2026-09-22 — Ticket 103, phase 1 : l'échelle de la cohorte c2

**Ce que c'est.** Les quatre références tabulaires et les trois planchers, joués sur c2 avec la
chaîne de véhicules et le verrou de retour actifs, graine 42, mode `sans_simulateur`. Ils fixent
le plafond et le plancher **de c2**, sans lesquels aucune mesure des phases 2 et 3 ne se lit.
Déterministes, sans appel de modèle de langue.

Tous dérivent de leur homologue c1 par `derive_de`, en ne changeant que la population et le jeu.

| Décideur | Composite EMD–JSD | L1 | Décidés | Fin (CEST) | Exécution |
|---|---:|---:|---:|---|---|
| Gradient boosté (LightGBM) | **2,5342** | 37,224 | 3159/3163 | 2026-09-22 19:12:52 | `2026-09-22_17_12_14` |
| Régression à noyau (KLR) | 2,9286 | 39,479 | 3159/3163 | 2026-09-22 19:13:34 | `2026-09-22_17_12_58` |
| Logit multinomial (MNL) | 3,2877 | 43,323 | 3159/3163 | 2026-09-22 19:11:57 | `2026-09-22_17_11_14` |
| Forêt aléatoire (RF) | 3,7085 | **37,200** | 3159/3163 | 2026-09-22 19:19:50 | `2026-09-22_17_15_01` |
| Durée minimale (plancher) | 23,5164 | 164,955 | 3159/3163 | 2026-09-22 19:14:32 | `2026-09-22_17_14_18` |
| Tout-voiture (plancher) | 28,8613 | 186,709 | 3159/3163 | 2026-09-22 19:14:10 | `2026-09-22_17_13_58` |
| Hasard uniforme (plancher) | 50,2795 | 265,476 | 3151/3163 | 2026-09-22 19:13:52 | `2026-09-22_17_13_40` |

Le gras marque le meilleur de chaque colonne ; composite et L1 se lisent vers le bas.

**Bande tabulaire c2 : [2,53 ; 3,71]** en composite. Pour mémoire, la même bande sur c1 vaut
[3,60 ; 4,09] — les deux ne se superposent pas, et c'est pourquoi un score c2 ne se compare
qu'à la bande c2.

**Sources :** `data/experiences/exp_{lgbm,klr,mnl,rf,durmin,majvoiture,alea}_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_nosim/executions/<exécution>/scores.json`
**Compteurs :** `…/executions/<exécution>/compteurs.json` · **état et heure de fin :** `…/etat.json`

**Rejouer :** `docker compose -f infra/docker-compose.yml --project-directory . exec -T controller python -m experiences lancer --experience <nom>`
La forêt aléatoire fait exception et passe par son lanceur dédié — elle a été estimée sous
scikit-learn 1.8.0 quand le conteneur porte la 1.9.0 :
`services/llm-agents/.venv/bin/python scripts/progedo_logit/lancer_experience_rf.py --vers exp_rf_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_nosim`

**Zéro erreur, zéro attente, aucun quota consommé.** Les 3 159 décisions sur 3 163 attendus
tiennent largement au-dessus du seuil d'alarme de 3 000 posé par le ticket ; les 4 manquantes
sont des déplacements sans solution, et 12 pour le hasard uniforme.

**Ce que cette entrée ne dit pas :** rien sur Jev ni sur Gemini hors échantillon. Les phases 2
et 3 du ticket 103 restent à jouer, et aucune question Q1 à Q3 n'est tranchée.

---
