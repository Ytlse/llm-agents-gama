# Étape 3a — Plan longitudinal : formation d'habitudes, choc, récupération

> **Ticket porteur :** [`docs/tickets/ticket_041_etape_3a_hysteresis_longitudinale.md`](../../../tickets/ticket_041_etape_3a_hysteresis_longitudinale.md)
> **Statut :** plan v0.1 du 2026-09-09, **à valider avant toute ligne de code** (règle plan-first).
> **Questions ouvertes :** [`specs/ticket_041/questions.md`](../../../../specs/ticket_041/questions.md) — avancé sous hypothèses, à trancher.
> **Ce que ce plan remplace :** la version « 5 jours » de l'Étape 3a (`MANUSCRIT_DETAILLE_2026.md` §5.1, fiches `exp_04a…d` de `experiments.yaml`) devient le **palier minimal** d'un dispositif à trois périodes qui va jusqu'à deux mois simulés.

---

## 0. En une page

**La question.** Un agent LLM doté d'une mémoire fait-il ce qu'un humain fait et qu'aucun modèle tabulaire ne peut faire : **former une habitude** en régime stable, **réagir** à un incident marquant, puis **revenir — ou pas — à son comportement antérieur** une fois la situation rétablie ?

**Le dispositif.** Une même cohorte scellée d'environ 100 à 200 agents (effectif à calibrer, §4) est jouée **trois fois** dans GAMA en mode offline, sur le même calendrier, la même météo, la même offre de transport et les mêmes graines :

| Bras | Décideur | Ce qu'il voit du passé |
|---|---|---|
| **M** — LLM + mémoire | modèle épinglé + meilleur prompt calibré | ses souvenirs (réflexions STM → LTM, rappel par similarité) |
| **A** — LLM amnésique | même modèle, même prompt | rien : chaque jour est le premier |
| **O** — oracle LightGBM | politique tabulaire sur 21 variables, renormalisée sur l'offre | rien, par construction |

sur un calendrier en **trois périodes** :

```
   P1 · Nominal (n1 jours)        P2 · Choc (1 à 3 jours)        P3 · Rétabli (n3 jours)
 ┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
 │ Convergence vers une     │   │ Incident déclaré deux    │   │ Réflexe d'évitement,     │
 │ habitude ? En combien de │──►│ fois : dans le graphe    │──►│ puis retour (ou non) au  │
 │ jours ? Taux de change-  │   │ (offre, retards) et en   │   │ nominal. Demi-vie, part  │
 │ ment journalier ?        │   │ langue (observations)    │   │ permanente, spécificité  │
 └──────────────────────────┘   └──────────────────────────┘   └──────────────────────────┘
```

**Ce qu'on mesure chaque jour, pour chaque agent et chaque déplacement récurrent :** la distribution de probabilité émise par le décideur, le mode tiré, l'exposition à l'incident, les souvenirs présentés, la justification textuelle, le coût en requêtes. Tout est archivé ; l'analyse vient après.

**Ce qu'on prédit, avant de lancer (§6).** Le bras **M** est le seul dont la distribution se **resserre** au fil des jours (habitude), le seul qui **évite encore** le mode perturbé le lendemain du choc alors que l'offre est redevenue nominale, et le seul dont le retour suit une **courbe** ajustable (demi-vie de quelques jours, part permanente de quelques points — l'ordre de grandeur de Larcom et al., 2017 : ≈ 5 %). Les bras **A** et **O** reviennent instantanément à leur régime nominal, à la variance du tirage près. Un choc **placebo** ne déplace rien ; les agents **non exposés** ne bougent pas.

**Ce qu'on ne prétend pas.** Aucune enquête ne suit les mêmes individus jour après jour autour d'un incident toulousain : la *valeur* d'un taux de reprise n'est comparable à rien. Ce qui est testable est l'**ordre des bras**, la **monotonie** du retour, la **sensibilité** aux paramètres de mémoire, et la **comparaison d'ordre de grandeur** avec les élasticités publiées après grèves, pannes et fermetures (§2). C'est une validation de **Tier 2** au sens de SILICA (Bin Tareaf et al., 2026), pas de Tier 3.

---

## 1. Ce que le dépôt permet aujourd'hui, et ce qui manque

Cartographie faite le 2026-09-09 sur la branche `feat_cache_population`. Elle conditionne le plan de travail (§8).

### 1.1 Acquis réutilisables

| Besoin | Acquis | Où |
|---|---|---|
| Horizon multi-jours | paramètre `simulation_max_days` (0..365), arrêt par `pause` de la simulation à l'horizon | `GAMA/CityTransport/models/City.gaml:72-75`, `sim_params.yaml` (**vaut 1 aujourd'hui**) |
| Bras amnésique | `make run OFFLINE=1 MEM=0` coupe LTM **et** auto-réflexion ; drapeau journalisé par décision | `Makefile:997-999`, `moves.csv` colonne `long_term_memory_enabled` |
| Mémoire persistante | LTM (ChromaDB + JSON shardés) **dans le répertoire du run**, relue au redémarrage ; mémoïsation des réflexions hors run | `llm/longterm.py`, `llm/reflection_store.py` |
| Reprise | `make stop-run` puis `make run OFFLINE=1 CONT=1` : même répertoire, journaux appendés, LTM retrouvée, GAMA repart à t0 du jour simulé | `settings.py:662-680`, `docs/setup/quickstart.md` |
| Oracle au même contrat que le LLM | `DecideurModele` (renormalisation sur l'offre, tirage seedé, artefact scellé SHA-256) | `llm-agents/experiences/decideur_modele.py` — **plateforme seulement** |
| Format d'événement | modèle `Evenement` (incident / information, jour, fenêtre, cible ligne/zone/tronçon, description) — **archivé mais refusé à l'exécution** | `llm-agents/experiences/experience.py:138-159, 530-537` |
| Observations vécues → mémoire | GAMA remonte `transfer`, `wait_in_stop`, `tc_timeout`, `arrival`, retards de reprogrammation ; chacun devient une entrée STM horodatée à l'heure murale | `simulation_controller.py:1457-1490` |
| Distribution de probabilité par décision | le LLM émet une distribution sur les modes, le mode est **tiré** (graine dérivée de agent × activité × jour) | `moves.csv`, `settings.py:444-451` |
| Randomisation de l'ordre des options | `option_order_seed` | `settings.py:453-458` |
| Météo sur 12 mois, GTFS sur l'année | `data/weather/meteo_toulouse_12_mois.csv`, `docs/arch/gtfs-annee.md` | — |
| Journaux | `moves.csv`, `llm_exchanges.jsonl` (prompts et réponses complets, `sim_day`), `agent_memory_events.jsonl`, checkpoint population quotidien à 2 h | `settings.py:564-586` |
| Quotas et rotation | `providers.yaml`, RPD appliqué, remise à zéro à 09:00 Paris pour Google | `config/llm_gateway/providers.yaml` |

### 1.2 Manques bloquants (à livrer avant la campagne)

1. **Aucun mécanisme d'événement n'est joué.** Ni dans GAMA, ni dans le contrôleur : le format existe, l'exécution le refuse (`plateforme-experiences.md:396-399`). Le canal WebSocket topiqué Python → GAMA (`system/throttle`) est le point de greffe naturel d'un `system/evenement`.
2. **L'oracle n'est pas branchable dans GAMA.** Le chemin de décision GAMA (contrôleur + passerelle) n'a pas de branche « modèle » ; `DecideurModele` ne vit que dans le mode sans simulateur.
3. **Le multi-jours est théorique.** Configuration à 1 jour ; post-traitements filtrant le premier jour (`frames.read_moves`, `common_set_eval.build_sample`) ; auto-réflexion LTM cadencée en RAM (repart de zéro à chaque `/init`) ; `state.json` jamais écrit ; pas de politique de calendrier (jours ouvrés) côté GAMA.
4. **La STM vit en RAM et meurt au redémarrage.** Une pause avant drainage perd les observations non encore réfléchies → biais du bras M. Le drainage nocturne existe (`[drainage] Réflexions STM épuisées`) mais la pause ne l'attend pas.
5. **Le décideur n'est pas épinglé dans le chemin GAMA.** La passerelle cascade vers un autre modèle sur épuisement (spec 05 Q2/Q3 livrées pour la plateforme, pas pour GAMA).
6. **Le cache de décisions est sémantique.** Une décision post-choc à contexte « presque identique » peut être servie par une décision pré-choc. Menace directe à la validité (§8, L1).
7. **Les souvenirs présentés ne sont pas tracés dans le chemin GAMA.** `decisions.jsonl` de la plateforme a le champ `souvenirs` ; `moves.csv` ne l'a pas.
8. **Le nettoyage LTM mélange heure murale et heure réelle** (`longterm.py:579-587`) : au-delà de 10 000 entrées, tous les `CONCEPT` seraient purgés d'un coup. Avec 100 agents × 60 jours × ~20 entrées/jour ≈ 120 000 entrées, **le seuil sera franchi**. À corriger avant.

### 1.3 Ce que la mémoire actuelle sait faire — et ne sait pas faire

Mesuré sur le run `2026-08-24_17_34` (930 agents, mémoire active) et lu dans le code :

- Rappel : requête d'embedding local (pas d'appel LLM) → 32 à 100 candidats filtrés par agent → re-classement `0,4·cosinus + 0,3·BLEU(tags) + 0,3·0,7^jours` → **top 3** entrées dans le prompt (défaut code `long_term_max_entries_query = 3`, la doc dit 10).
- **Décroissance temporelle 0,7 par jour** : demi-vie ≈ 1,9 jour. Un souvenir de 5 jours pèse 17 % de son poids initial dans le terme temporel. Autrement dit : **l'architecture actuelle ne peut pas porter une habitude au-delà d'une semaine** autrement que par des réflexions/concepts génériques (« je prends toujours le métro »), qui n'ont pas de mécanisme de renforcement.
- Pas de notion d'importance à l'écriture (le champ `importance_score` de la doc n'existe pas), pas de renforcement par répétition, pas de structure « habitude » : le mot n'existe que comme consigne de prompt (`ltm_self_reflection/template.md.j2:30`).
- Coût : **≈ 2,3 tâches « choix » + ≈ 1,1 tâche « réflexion STM »** par agent et par jour plein (auto-réflexion LTM : 1 par agent tous les 3 jours, jamais observée sur un run < 3 jours). Les tâches sont regroupées par la passerelle : ~10 agents par requête pour les décisions (cible `batch_target_agents`, capacité Gemini 15), **~3,5 réflexions par requête** mesurées.

Conséquence pour le manuscrit : la formule $w_m(t) = 1 - \sum \gamma \cdot \frac{\Delta t_{\text{retard}}}{\Delta t_{\text{ref}}} e^{-\lambda (t - t_k)}$ du §5.1 **ne décrit pas le code**. `γ` et `λ` n'existent nulle part ; le seul paramètre apparenté est `long_term_retrieval__time_decay = 0,7`, soit $\lambda = -\ln 0{,}7 \approx 0{,}36$ par jour (proche du 0,4 de la fiche `exp_04a`). Le plan tranche (§6.4) : la formule devient un **modèle descriptif ajusté a posteriori** sur les courbes observées, et le bras de sensibilité « λ ÷ 3 » se joue sur `time_decay` ($e^{-0{,}36/3} \approx 0{,}89$).

---

## 2. Ce que la littérature observe dans la réalité

Ancrage vérifié le 2026-09-09 (rapport complet à archiver dans `docs/paper/sources/BIBLIOGRAPHIE.md`, section à créer « Habitudes, perturbations, récupération »). Les chiffres ci-dessous servent de **cibles d'ordre de grandeur** pour les prédictions du §6, jamais de vérité terrain.

### 2.1 Période 1 — formation des habitudes

| Fait | Chiffre | Source |
|---|---|---|
| L'habitude est une réponse déclenchée par le contexte, sans médiation par l'intention ; on la change en agissant sur les indices | — | Wood & Neal (2007), *Psychological Review* |
| Forte habitude modale ⇒ moins d'acquisition d'information, choix moins élaboré | 3 études | Verplanken, Aarts & van Knippenberg (1997), *EJSP* |
| Temps d'atteinte du plateau d'automaticité pour un comportement quotidien | **médiane 66 jours**, étendue 18–254 ; sauter une occasion ne casse pas la courbe | Lally et al. (2010), *EJSP*, doi 10.1002/ejsp.674 |
| Répétitivité jour-à-jour : « ni totalement répétitive ni totalement variable », plus stable les jours travaillés | panel 6 semaines Mobidrive | Schlich & Axhausen (2003), *Transportation* |
| Répétitivité du **mode** liée au lieu d'activité plus qu'à l'activité | indice de Herfindahl | Susilo & Axhausen (2014), *Transportation* |
| Part d'unimodaux sur une semaine | **44 %** unimodaux, 56 % multimodaux (NTS GB, 7 jours) | Heinen & Chatterjee (2015), *TR-A* |
| Stabilité annuelle des automobilistes | **1 sur 10** change de mode d'une année à l'autre ; changements portés par les événements de vie | Clark, Chatterjee & Melia (2016), *TR-A* |
| Fenêtre de redélibération après changement de contexte (déménagement) | effet décroissant avec le temps écoulé | Verplanken et al. (2008) ; Thomas, Poortinga & Sautkina (2016), *PLOS ONE* |

**Lecture pour le plan.** Un agent qui a 2 à 3 déplacements récurrents par jour et une mémoire à demi-vie de 2 jours ne peut pas reproduire 66 jours de consolidation ; il faut donc **mesurer** si une convergence apparaît, en combien de jours, et sous quelle forme (resserrement de la distribution, réflexions « habitude »). La cible n'est pas 66 jours, c'est : *converge-t-il, et le bras amnésique ne converge-t-il pas ?*

### 2.2 Période 2 — réaction à un événement marquant

| Événement | Réaction observée | Source |
|---|---|---|
| Grève métro Londres, 2 jours (fév. 2014), > 200 M de validations | forte redistribution des itinéraires pendant ; **≈ 5 % conservent le nouvel itinéraire après** | Larcom, Rauch & Willems (2017), *QJE* |
| 13 grèves TC, revue + enquête | 10–20 % des déplacements annulés ; report majoritaire voiture ; **perte de part TC à long terme 0,3–2,5 %** | van Exel & Rietveld (2001), *Transport Policy* |
| Grève LA Metro 2003 | +47 % de retard autoroutier | Anderson (2014), *AER* |
| Fermeture 8 jours d'une autoroute urbaine (Hanshin) | bascule TC inversement liée à l'habitude voiture ; correction de la surestimation du temps TC | Fujii, Gärling & Kitamura (2001), *Env. & Behavior* |
| Effondrement I-35W (Minneapolis 2007) | **plusieurs semaines** de ré-équilibrage ; évitement initial de la zone puis retour progressif | Zhu et al. (2010), *TR-A* ; Danczyk et al. (2017), *Transport Policy* |
| JO Londres 2012, panel 1 132 navetteurs | 54 % ont changé au moins une chose (surtout horaires) | Parkes, Jopson & Marsden (2016), *TR-A* |
| Quasi-accidents vélo | 86 % en ont vécu ; ~1 incident « très effrayant » sur 60 fait envisager d'arrêter | Sanders (2015), *AAP* ; Aldred (2016), *TR-A* |
| Vol de vélo | **11 % des victimes abandonnent le vélo** | ADMA/FUB [V-partiel] |
| Accident de voiture | anxiété de conduite 18–77 % selon populations ; évitement de situations | revues Taylor & Koch [V-partiel] |
| COVID-19 | TC −80 à −90 % ; réaction dès l'**annonce** (MOBIS-Covid) | Bucsky (2020) ; Molloy et al. (2021), *Transport Policy* |

### 2.3 Période 3 — rétablissement, hystérésis, constantes de temps

| Fait | Chiffre | Source |
|---|---|---|
| Part permanente après choc court | ≈ 5 % d'itinéraires changés durablement | Larcom et al. (2017) |
| Perte permanente TC par grève | 0,3–2,5 % | van Exel & Rietveld (2001) |
| Rétablissement du trafic après rupture d'infrastructure | semaines | Zhu et al. (2010) |
| Incitation positive de 3 mois (9-Euro-Ticket) | usage régulier TC 29 % → 38 % → **32 %** après : ≈ 1/3 de la hausse conservée à un mois | Loder et al. (2024), *CSTP* |
| Ticket bus gratuit 1 mois, automobilistes habitués | effet encore mesurable **1 mois après** | Fujii & Kitamura (2003), *Transportation* |
| Demi-vie formelle du retour à l'habitude | **aucune source ne la publie** ; ordres de grandeur : jours-semaines (trafic), mois (attitudes), 1–5 % de bascule permanente | synthèse |

### 2.4 Mécanismes psychologiques → prédictions

- **Récence / disponibilité** (Tversky & Kahneman, 1973) : le dernier événement pèse plus que sa fréquence — prédit un évitement fort à J+1 qui décroît.
- **Biais de négativité** (Baumeister et al., 2001) : « bad is stronger than good » — prédit qu'un choc négatif laisse une trace plus durable qu'une incitation positive de même ampleur (§6, P7).
- **Règle pic-fin** (Kahneman et al., 1993) : un retard de 45 min à l'arrivée pèse plus que 3 × 15 min répartis.
- **Inertie par apprentissage** (Chorus & Dellaert, 2012 ; Cantillo, Ortúzar & Williams, 2007 ; Cherchi & Manca, 2011) : répéter le choix passé même quand une alternative devient meilleure.
- **Lissage exponentiel des temps vécus** en affectation dynamique jour-à-jour (Horowitz, 1984 ; Cascetta, 1989 ; Cantarella & Cascetta, 1995) : c'est le **modèle de référence** dont la formule du manuscrit est un cas particulier ; il donne un sens interprétable au paramètre de décroissance.

### 2.5 Architectures mémoire d'agents génératifs

Park et al. (2023) — flux mémoire, score récence × importance × pertinence, réflexion ; MemoryBank (Zhong et al., AAAI-24) — **courbe d'oubli d'Ebbinghaus avec renforcement** ; A-MEM (Xu et al., NeurIPS 2025) ; Mem0 (2025) ; HippoRAG (NeurIPS 2024). En mobilité : LLMob (Wang et al., NeurIPS 2024 — « motifs habituels + motivations courantes »), CoPB (Shao et al., 2024), AgentMove (NAACL 2025), CitySim (EMNLP 2025), **GATSim** (Liu et al., 2025 — mémoire hiérarchique, **réflexion hebdomadaire formant préférences et habitudes**), AgentSociety (2025). Un précédent direct : architecture cognitive multi-horizon testée sur une **grève de taxis à 80 % aux jours 11–15 d'un run de 20 jours**, avec ablation des mémoires court/long terme (*Sensors* 25(18), 5688, 2025). C'est le point de comparaison le plus proche de ce plan ; notre apport est l'oracle tabulaire comme troisième bras et la population issue d'une enquête réelle.

---

## 3. Hypothèses et questions de recherche

**H3 (manuscrit, inchangée) :** l'agent LLM avec mémoire présente une dynamique temporelle non indépendante (hystérésis) que ni l'agent amnésique ni le modèle tabulaire ne présentent.

Déclinée en quatre sous-hypothèses testables, chacune avec sa métrique principale (§5) et son critère de réfutation (§6) :

- **H3-a · Formation.** En régime nominal, la distribution émise par le bras M pour un déplacement récurrent se **resserre** au fil des jours ; celle des bras A et O reste stationnaire.
- **H3-b · Réaction.** Le jour du choc, les trois bras réagissent à la **contrainte physique** (offre dégradée) ; seul M réagit aussi à **l'expérience vécue** (observation de retard) pour ses décisions ultérieures dans la journée.
- **H3-c · Hystérésis.** À J+1 et au-delà, offre redevenue nominale, seul M continue d'éviter le mode perturbé ; le retour est **monotone**, de demi-vie mesurable, avec une part permanente $c \ge 0$.
- **H3-d · Spécificité.** L'effet est porté par l'**exposition** (agents ayant vécu le retard) et par la **pertinence** du choc (un placebo ne déplace rien) ; il dépend du paramètre de décroissance de la mémoire.

**Questions exploratoires** (déclarées comme telles, non confirmatoires) : hétérogénéité par profil (§4.3) ; asymétrie choc négatif / incitation positive ; contenu des justifications (le modèle cite-t-il l'incident, et combien de jours ?) ; effets de bord des réflexions génériques (« habitude » auto-déclarée).

---

## 4. Design expérimental

### 4.1 Bras

| Bras | Décideur choix | Décideur mémoire | Mémoire | Obligatoire |
|---|---|---|---|---|
| **M** | modèle épinglé + prompt épinglé | modèle épinglé (le même ou un second, §4.5) | active (config courante) | oui |
| **A** | idem M | — | coupée (`MEM=0`) | oui |
| **O** | LightGBM `mode_choice_policy.json@sha`, renormalisé sur l'offre | — | — | oui |
| **M-λ** | idem M | idem M | `time_decay` 0,7 → 0,89 (λ ÷ 3) | oui (réfutation ii) |
| **M-placebo** | idem M | idem M | active ; choc **placebo** (§4.4) | oui (réfutation iii) |
| **M-news** | idem M | idem M | active ; incident annoncé **par article** aux non-exposés | optionnel (pont avec Étape 3b) |
| **M2…M4** | idem M | idem M | variantes de mémoire (§7) | optionnel, budget |
| **M-bis** | seconde famille de modèles | idem | active | optionnel (Tier 2 : stabilité inter-modèles) |

Règles communes à tous les bras : même population, mêmes graines (`population_sample_seed`, `mode_draw_seed`, `option_order_seed`, `weather_draw_seed`), même calendrier, même météo, même offre GTFS/OTP, même événement déclaré au même instant. Température **0**. Ordre des options randomisé par requête. **Aucune substitution de modèle** (spec 05 Q3) — l'exécution attend le renouvellement du quota ; jamais de repli.

### 4.2 Calendrier

Trois paliers, du minimal (compatible avec les fiches `exp_04a…d`) à l'étendu (deux mois) :

| Palier | P1 nominal | P2 choc | P3 rétabli | Total | Usage |
|---|---|---|---|---|---|
| **Minimal** | 1 j | 1 j | 3 j | 5 j | manuscrit actuel ; test de bout en bout |
| **Standard** | 10 j | 1 j | 15 j | 26 j | campagne principale (5 semaines ouvrées) |
| **Étendu** | 20 j | 1–3 j | 37–39 j | 60 j | hystérésis longue ; formation d'habitudes |

**Hypothèse de calendrier (question Q1) :** on simule les **jours ouvrés seulement**, la date avançant du vendredi au lundi (les chaînes d'activités EQASIM sont des journées de semaine ; l'offre GTFS et la météo restent datées correctement). 60 jours simulés = 12 semaines calendaires. Départ : lundi 16 mars 2026 (valeur actuelle de `starting_date`).

**Choix de n1 et n3.** Le pilote L0 (§8) mesure le jour de stabilisation $T^\*$ ; n1 doit valoir au moins $T^\* + 5$ pour que le choc frappe une habitude formée, sinon on mesure la réaction d'un agent encore en exploration. n3 doit couvrir au moins trois demi-vies estimées au palier minimal.

### 4.3 Population et profils

- **Source** : population scellée `population_1000_AAMAS_v5` (sha256 gelé), **sous-échantillon par ménages entiers** (la chaîne des véhicules du foyer reste cohérente), tirage stratifié à graine fixe, effectif $N$ à calibrer (§4.6).
- **Strates de profil** (quotas déclarés, sur-représentation assumée et **repondérée** pour les agrégats) :

| Profil | Définition (variables du contrat de 21) | Pourquoi |
|---|---|---|
| Captif TC | pas de voiture disponible, abonnement TC | exposé au choc métro ; test de la contrainte |
| Multimodal urbain | voiture + vélo + TC accessibles, 1ʳᵉ couronne | le seul qui **peut** changer : là où l'hystérésis se lit |
| Dépendant voiture périurbain | 2ᵉ/3ᵉ couronne, 2 voitures | choc rocade ; inertie attendue |
| Cycliste | `has_bike`, déplacements < 5 km | choc individuel (chute, vol) ; météo |
| Étudiant | `main_occupation` étudiant, 18–24 | flexibilité horaire (Pnevmatikou et al., 2015) |
| Senior | ≥ 65 ans | sensibilité sécurité / confort |

- Le profil est **enregistré** par agent dans le panel ; les analyses par profil sont exploratoires.

### 4.4 Catalogue d'incidents

Chaque incident est **déclaré deux fois** (manuscrit §5.3) : en **graphe** (ce que l'offre et les durées montrent à tous les bras, oracle compris) et en **langue** (ce que l'agent vit et mémorise). Prédictions directionnelles signées **avant** tout appel, gelées par empreinte git.

| # | Incident | Portée | Durée | Encodage graphe | Encodage langue | Modes touchés (prédiction signée) | Ancrage |
|---|---|---|---|---|---|---|---|
| **I1** | Panne informatique métro ligne A, 17 h → fin de service | collectif | 1 j | légs ligne A supprimés ou +45 min après 17 h | observation `tc_timeout` / arrivée en retard pour les agents à bord ou en attente | TC −− ; voiture + ; marche + | fiche `exp_04a` ; pannes réelles A (août–sept. 2026) |
| **I2** | Grève TC (bus, tram, métro) | collectif | 3 j | fréquences ÷ 3, lignes fermées selon préavis | observations d'attente ; article de préavis la veille | TC −− ; voiture ++ ; vélo + | Larcom 2017 ; van Exel 2001 ; grèves Tisséo 2023 |
| **I3** | Rocade coupée (accident grave), +60 min | collectif | 1 j | durées voiture +60 min sur les OD traversant le tronçon | observation de retard voiture | voiture − ; TC + ; train + | Zhu 2010 ; manuscrit §5.2 |
| **I4** | Chute de vélo (agent seul) | **individuel** | 1 j | aucun | observation « chute, blessure légère » ; vélo indisponible le lendemain | vélo −− (l'agent) ; rien (les autres) | Sanders 2015 ; Aldred 2016 |
| **I5** | Vol de vélo (agent seul) | individuel | permanent jusqu'à rachat (J+7) | `has_bike = false` 7 j | observation | vélo −− puis retour ? | FUB : 11 % abandonnent |
| **I6** | Canicule + pic d'ozone | collectif | 3 j | météo 38 °C ; tarif TC réduit (texte) | observation météo ; arrêté préfectoral | vélo − ; marche − ; TC + | manuscrit §5.2 ; Böcker 2013 |
| **I7** | Pénurie de carburant | collectif | 3 j | voiture indisponible pour 30 % des ménages (tirage) | observation « station à sec » | voiture − ; TC + ; vélo + | oct. 2022 |
| **I8** | Neige / verglas | collectif | 1 j | bus suspendus, durées voiture ×1,5, vélo indisponible | observation météo | vélo −− ; bus − ; métro + | épisodes toulousains |
| **I9** | **Placebo** : grève des éboueurs (odeurs hypercentre) | collectif | 3 j | aucun | article | **aucun** effet modal attendu | grille des 30 articles (n° 7 → réserve placebo) |
| **I10** | **Incitation positive** : mois de TC gratuit | collectif | 20 j | coût TC = 0 (texte) | observation | TC + pendant ; **retour partiel** après | Fujii & Kitamura 2003 ; Loder 2024 |
| I11 | Perte de permis (agent seul) | individuel | 30 j | `has_driving_license = false` | observation | voiture −− ; TC/vélo + | aucune étude identifiée |
| I12 | Fermeture d'une passerelle piétonne / travaux | local | 10 j | détour marche +10 min sur une zone | observation | marche − | Guiver 2011 |

**Priorité de campagne** : I1 (principal, comparable au manuscrit) → I9 placebo (obligatoire) → I4 individuel (le seul cas où **rien** dans le graphe ne change : mémoire pure) → I2 grève multi-jours → I10 incitation positive (asymétrie) → les autres selon budget. Les chocs individuels sont appliqués à un sous-ensemble tiré à graine fixe (par exemple 30 % des cyclistes), les autres servant de **témoins internes**.

### 4.5 Modèles et prompt

- **Un seul modèle de choix pour tous les bras LLM d'une même campagne.** Recommandation : `gemini-3.5-flash-lite` + prompt `expert_chaine_m5` (meilleur composite mesuré, 12,6), deux clés Google → 1 000 RPD. (Le « gemini flash 1.5 » de la demande n'est plus dans la rotation ; les instances actuelles sont 3.1 et 3.5 flash-lite.)
- **Modèle de mémoire distinct autorisé** (idée de la demande) : les réflexions STM et l'auto-réflexion LTM peuvent être servies par `mistral-small-latest` (sans RPD, garde-fou tokens), ce qui **supprime le goulot de quota** du bras M (§4.7). Condition : le même modèle de mémoire sur **tous** les bras à mémoire, déclaré dans le registre, et un bras de contrôle « mémoire écrite par le modèle de choix » sur le palier minimal pour vérifier que la plume du rédacteur ne change pas la conclusion (question Q3).
- **Gel** : checksum du prompt système, identifiants de modèles, `providers.yaml` et `sim_params.yaml` archivés dans le répertoire du run (déjà fait pour `static_config.yaml` / `scenario_params.yaml`).

### 4.6 Effectif : calibrer $N$ par la puissance, pas par le budget seul

L'unité d'analyse de H3-c est **l'agent exposé** (a vécu le retard) et le contraste est **apparié** entre bras (même agent, même jour, mêmes graines) : McNemar sur la bascule modale, puis modèle mixte (§6.2).

Ordre de grandeur, deux proportions indépendantes, $\alpha = 0{,}05$, puissance 0,8, référence $p_0 = 0{,}80$ (part de reprise du mode perturbé chez les bras A et O, valeur du manuscrit) :

| Écart à détecter (M vs A) | $n$ agents exposés par bras |
|---|---|
| 10 pt | ≈ 290 |
| 15 pt | ≈ 140 |
| 20 pt | ≈ 80 |
| 30 pt | ≈ 40 |

Le plan apparié divise ces effectifs par 3 à 10 (manuscrit §2.3). **Pour I1, les exposés sont les usagers du métro A après 17 h** : avec $N = 100$ agents et une part TC de 12–16 %, on en compte **15 à 25** — insuffisant pour un écart de 20 pt même apparié. D'où la stratification (§4.3) : **$N = 200$ avec un quota de 60 agents au moins captifs ou abonnés TC** est le point de départ recommandé ; le pilote L0 mesure la part réellement exposée et ajuste. Pour I3 (rocade) les exposés sont majoritaires ; pour I4/I5 (individuels) l'effectif exposé est **choisi** par tirage.

Toute publication porte l'effectif (règle 3 du protocole), les IC par **cluster bootstrap par agent**, et un témoin d'effectif sans appel au modèle.

### 4.7 Coût, quotas et durée : le simulateur

**Coefficients mesurés** (run `2026-08-24_17_34`, à re-mesurer au pilote L0 sur $N$ agents) :

| Poste | tâches / agent-jour | tâches / requête | requêtes / agent-jour |
|---|---|---|---|
| choix (`itinary_multi_agent`) | 2,3 | 10 | 0,23 |
| réflexion STM (`stm_reflection`) | 1,1 (régime établi : jusqu'à 2,0) | 3,5 | 0,31 (max 0,57) |
| auto-réflexion LTM (tous les 3 j) | 0,33 | 3,5 | 0,10 |
| **bras M** | | | **≈ 0,64** (max 0,90) |
| **bras A** | | | **0,23** |
| **bras O** | | | 0 |

**Formule** :
$$J_{\min} = \left\lceil \frac{N \cdot D \cdot \sum_{\text{bras}} q_{\text{bras}}}{\text{RPD}_{\text{disponible}} \cdot (1 - m)} \right\rceil$$
avec $q$ en requêtes/agent-jour, $m$ = marge pour reprises et erreurs (20 %), et **la contrainte RPD porte sur le modèle de choix** (les réflexions passent sur le modèle de mémoire si celui-ci est sans RPD).

**Application, palier étendu ($D = 60$), 1 000 RPD sur le modèle de choix :**

| Configuration | Requêtes de choix | Requêtes de mémoire | Jours de quota (choix, 1 000 RPD, m = 20 %) |
|---|---|---|---|
| $N = 100$, bras M + A + O | 2 × 1 380 = 2 760 | 2 460 | **4 j** (mémoire sur Mistral : hors goulot) |
| $N = 100$, + M-λ + M-placebo | 4 × 1 380 = 5 520 | 7 380 | **7 j** |
| $N = 200$, 5 bras LLM | 11 040 | 14 760 | **14 j** |
| $N = 200$, 5 bras × 3 graines pour M | 11 040 + 2 × 2 760 | … | **21 j** |
| même chose, mémoire aussi sur Gemini | 25 800 | — | **33 j** |

Exemple demandé dans la demande — 1 000 RPD, 2,1 requêtes choix + 0,9 mémoire **par agent-jour non regroupées**, 100 agents, 60 jours : sans regroupement il faudrait $100 \times 60 \times 3{,}0 / 800 = 22{,}5$ jours par bras ; avec le micro-batching mesuré, **4 jours pour les trois bras**. Le regroupement est le levier n° 1 ; l'externalisation de la mémoire vers un fournisseur sans RPD le n° 2.

**Temps réel** : à 15 RPM par clé, un jour simulé de 100 agents en bras M (≈ 64 requêtes) tient en quelques minutes de passerelle ; le pas GAMA domine. Le pilote L0 mesure le ratio temps réel / temps simulé et le publie dans le registre.

**Livrable** : `scripts/AAMAS/simulateur_cout_longitudinal.py` — entrées (N, D, bras, coefficients mesurés, RPD par instance, marge), sorties (requêtes par bras et par jour, jours de quota, calendrier de campagne tenant compte de la remise à zéro à 09:00 Paris) ; lit `providers.yaml` pour les quotas, jamais une constante.

---

## 5. Collecte : tout enregistrer, décider après

Principe : **mieux vaut trop de données**. Chaque bras produit un répertoire d'exécution autoportant ; l'analyse ne lit que ces répertoires.

### 5.1 Par décision (grain le plus fin) — `decisions.parquet`

| Champ | Source | Existe |
|---|---|---|
| bras, run_id, graines, empreintes (population, prompt, modèle, politique) | registre | partiel |
| `person_id`, `activity_id`, profil, ménage | population | oui |
| jour simulé (index P1/P2/P3 et **date**), heure de départ prévue et réelle | `moves.csv` | oui |
| période relative à l'événement (`avant` / `pendant` / `après`, jours depuis le choc) | événement | **à ajouter** (G9) |
| **exposition** : l'agent a-t-il subi l'incident (retard vécu, ligne empruntée, observation reçue) | contrôleur | **à ajouter** |
| options présentées (modes, durées, ordre randomisé), options écartées et motifs | `moves.csv` | oui |
| **distribution de probabilité émise**, mode tiré, méthode de sélection | `moves.csv` | oui |
| **souvenirs présentés** (identifiants, types, dates, texte) | LTM | **à ajouter** dans le chemin GAMA (existe dans `decisions.jsonl` plateforme) |
| justification textuelle (`reasoning`) | `moves.csv` | oui |
| prompt et réponse complets, tokens, fournisseur payeur, latence, cache hit/miss | `llm_exchanges.jsonl`, `llm_cache_hits.jsonl` | oui |
| météo du créneau | `moves.csv` | oui |
| résultat vécu : heure d'arrivée réelle, retard, événements GAMA du trajet | `gama_results/diff_arrival_time.csv`, observations | oui (à joindre) |

### 5.2 Par agent et par jour — `panel_agent_jour.parquet`

Modes tirés par déplacement récurrent ; indice de concentration $\sum_m p_m^2$ et entropie normalisée de la distribution émise ; mode dominant sur fenêtre glissante 5 j ; changement vs veille ; exposition cumulée ; nombre d'entrées STM écrites, réflexions produites, concepts créés ; taille de la LTM ; requêtes consommées par catégorie ; retard cumulé vécu.

### 5.3 Par jour — `journal_jour.parquet` et instantanés

Parts modales (brutes et repondérées par profil) ; parts par profil ; compteurs de coût par catégorie et par instance ; **instantané quotidien de la LTM** (export JSON des entrées par agent, déjà 26 Mo pour 930 agents : trivial pour 200) ; contenu de la STM à 2 h avant drainage ; checkpoint de population (existe) ; état des quotas ; `[ALARME]` levées ; durée réelle de la journée simulée.

### 5.4 Mémoire : audit dédié — `memoire_audit.parquet`

Pour chaque entrée LTM : date d'écriture (murale), type, texte, tags, provenance (lot STM, auto-réflexion), **nombre de fois présentée** dans un prompt et à quelles dates, score de rappel obtenu. Pour chaque réflexion : lot d'observations d'origine (pour lier « retard de 45 min le J12 » → « réflexion J12 » → « présentée J13, J14, J17 »). C'est ce qui permettra de dire *par quel chemin* l'hystérésis passe.

### 5.5 Événement — `evenement.yaml` archivé + `exposition.parquet`

Déclaration complète (format `Evenement` étendu : encodage graphe et encodage langue séparés), horodatage réel de l'injection, liste des agents effectivement exposés avec la nature de l'exposition (retard subi en minutes, observation reçue, article vu).

### 5.6 Codage des justifications

Un passage a posteriori (regex puis juge LLM **hors campagne**, modèle distinct, grille gelée) code chaque `reasoning` : mentionne l'incident ? mentionne une habitude ? mentionne un souvenir daté ? Produit la courbe « part des décisions citant l'incident » par jour — la **saillance déclarée**, à mettre en regard de la courbe comportementale.

---

## 6. Analyse et protocole statistique

### 6.1 Métriques par période

**P1 — formation.**
- $C_{i,a,t} = \sum_m p_m^2$ : concentration de la distribution émise (agent $i$, déplacement récurrent $a$, jour $t$). Habitude ⇔ $C$ croît vers 1. Métrique **indépendante du tirage**.
- $S_{i,a,t} = \mathbb{1}[\text{mode}_t \ne \text{mode}_{t-1}]$ : taux de changement journalier. Plancher théorique en tirage i.i.d. : $1 - \sum_m p_m^2$ — c'est ce que les bras A et O doivent afficher ; M doit passer dessous.
- $T^\*_{i,a}$ : premier jour à partir duquel le mode dominant tient ≥ 80 % sur 5 jours ; distribution de $T^\*$ par bras et par profil.
- Part d'agents unimodaux par semaine (comparable aux 44 % de Heinen & Chatterjee, à titre indicatif).

**P2 — réaction.**
- $\Delta_{\text{jour J}}$ : écart de part du mode perturbé, décisions **après** l'heure de l'incident, par bras — mesure la réaction à la contrainte physique (tous les bras) et, pour M, l'ajout de l'expérience vécue.
- Déplacements annulés / reprogrammés (comparaison aux 10–20 % de van Exel & Rietveld).

**P3 — hystérésis.**
- $\delta_{a,t} = \text{part}_{\text{pré}} - \text{part}_t$ du mode perturbé chez les **exposés**, $t = 1 \ldots n_3$.
- Ajustement $\delta_t = A\,e^{-t/\tau} + c$ : $\tau$ (demi-vie $= \tau \ln 2$), $c$ (part permanente), IC par bootstrap par agent. Comparer $c$ à l'intervalle 0,3–5 % de la littérature — **à titre d'ordre de grandeur**.
- Survie : délai jusqu'au premier retour au mode pré-choc chez les exposés ayant basculé (Kaplan-Meier par bras).
- **Différence de différences** : exposés vs non exposés × avant vs après, par bras. Les non exposés sont le témoin interne indispensable.
- Saillance déclarée (§5.6) vs comportement : le modèle cesse-t-il de citer l'incident avant ou après de cesser de l'éviter ?

### 6.2 Tests

- Contrastes appariés entre bras (même agent, même jour) : **McNemar** sur la bascule modale ; IC par cluster bootstrap par agent (1 000 ré-échantillonnages).
- Modèle principal : régression logistique mixte $\Pr(\text{mode perturbé})_{i,t} \sim \text{bras} \times \text{période} \times \text{exposé} + (1 \mid \text{agent}) + (1 \mid \text{jour})$ ; l'interaction triple est l'estimateur de H3-c.
- Retour au nominal : **test d'équivalence (TOST)** part$_t$ vs part$_{\text{pré}}$ avec borne ± 2 pt (déclarée), et non un test de non-significativité.
- Corrections de multiplicité (Holm) sur les hypothèses confirmatoires ; les analyses par profil et de justification sont exploratoires et étiquetées ainsi.
- Réplication : ≥ 3 graines de tirage (`mode_draw_seed`) pour le bras M sur le palier standard ; la dispersion inter-graines est la barre d'erreur minimale de toute affirmation.

### 6.3 Prédictions pré-enregistrées (à geler par empreinte git avant le premier appel)

| # | Prédiction | Réfutée si |
|---|---|---|
| P1 | $C_{M,t}$ croît en P1 ; $C_{A,t}$ et $C_{O,t}$ stationnaires | pente de $C_M$ dans l'intervalle de la pente de $C_A$ |
| P2 | $S_M$ passe sous le plancher $1 - \sum p^2$ de A avant la fin de P1 | non |
| P3 | Jour J : les trois bras évitent le mode perturbé (offre) ; l'écart M − A du jour J est > 0 pour les décisions postérieures à l'incident | écart M − A nul le jour J |
| P4 | J+1 : part du mode perturbé chez les exposés, $M < A \approx O$ ; A et O dans l'IC de leur régime pré-choc | A montre la même inertie que M (critère i du manuscrit) |
| P5 | Retour monotone de M, $\tau$ entre 1 et 15 jours, $c \in [0, 10]$ pt, $c_M > c_A = 0$ | non monotone, ou $c_M$ dans l'IC de $c_A$ |
| P6 | $\tau_{M\text{-}\lambda} > \tau_M$ (oubli plus lent ⇒ retour plus lent) | courbe M-λ dans l'IC de M (critère ii) |
| P7 | Placebo : $\delta$ dans l'IC du bruit ; non exposés : idem | placebo ≈ incident (critère iii) |
| P8 | Choc individuel I4 : effet chez les agents frappés, rien chez les autres, rien chez A et O | effet chez les non frappés |
| P9 | Asymétrie : $\lvert c \rvert$ après I1 (négatif) > $\lvert c \rvert$ après I10 (positif) à ampleur comparable | inverse ou égal |

### 6.4 Statut de la formule $w_m(t)$ du manuscrit

Elle n'est **pas implémentée** et ne doit pas l'être dans le prompt (ce serait dicter la réponse). Elle devient le **modèle descriptif** ajusté sur $\delta_t$ (§6.1), avec $\gamma$ estimé par l'amplitude $A$ rapportée au retard subi et $\lambda = 1/\tau$. Le manuscrit §5.1 est à réécrire en ce sens.

---

## 7. Améliorer la mémoire : pistes sourcées et échelle d'ablation

Constat (§1.3) : la mémoire actuelle oublie en deux jours et ne renforce rien. Elle **peut** produire une hystérésis courte (J+1, J+2) ; elle ne peut pas produire une habitude. Les pistes ci-dessous sont des **bras supplémentaires** (M2…M4), jamais des modifications du bras M de référence en cours de campagne. Aucune ne met la formule du manuscrit dans le prompt.

| Variante | Mécanisme | Source | Ce qu'elle teste |
|---|---|---|---|
| **M2 · importance à l'écriture** | chaque réflexion reçoit un score d'importance (LLM, 1–10) ; le rappel devient récence × importance × pertinence | Park et al. (2023) ; biais de négativité (Baumeister, 2001) | un retard de 45 min doit peser plus qu'un trajet ordinaire |
| **M3 · oubli avec renforcement** | force d'un souvenir $= e^{-t/S}$, $S$ croissant à chaque rappel ou répétition (Ebbinghaus) ; les expériences répétées deviennent quasi permanentes | MemoryBank (Zhong et al., AAAI-24) | formation d'habitude par répétition ; l'incident unique s'efface, l'habitude reste |
| **M4 · registre d'habitudes explicite** | compteur par (déplacement récurrent, mode) lissé exponentiellement — le modèle classique de Horowitz/Cascetta — rendu **en langue** dans le prompt (« ces 10 derniers jours : métro 8 fois, vélo 2 fois ; dernier retard métro : 45 min il y a 3 jours ») | Horowitz (1984) ; Cantarella & Cascetta (1995) ; SRHI (Verplanken & Orbell, 2003) | le LLM raisonne sur une statistique honnête de son propre passé au lieu de 3 extraits |
| **M5 · réflexion périodique d'habitude** | auto-réflexion hebdomadaire dédiée : « quelles sont mes routines, qu'est-ce qui les a perturbées » | GATSim (Liu et al., 2025) ; Generative Agents | consolidation ; effet des réflexions génériques |
| **M6 · pic-fin** | la réflexion STM reçoit explicitement le pire et le dernier événement du lot | Kahneman et al. (1993) | saillance de l'incident |

Corrections préalables, **hors ablation** (elles réparent, elles ne changent pas la conception) : nettoyage LTM à l'heure murale ; `last_reflection` persisté ; `long_term_max_entries_query` aligné doc/code ; STM drainée avant toute pause.

Recommandation d'ordre : M4 en premier (coût nul en requêtes, lisible, directement comparable au modèle économétrique), puis M3, puis M2. Chaque variante est un bras du palier standard, avec l'oracle et l'amnésique comme ancrage commun.

---

## 8. Plan de travail : lots, portes, dépendances

Aucun code avant validation de ce plan (porte G0). Chaque lot a sa spec dans `specs/ticket_041/` avant implémentation (méthode spec-first).

```
 G0 valider le plan
  │
  ▼
 L0 · Pilote sans code (2 j)            ─►  G1 : coefficients de coût, T*, part exposée, ratio temps réel
  │   MEM=1, N=100 (sous-pop scellée),         → fixe N, n1, n3 ; alimente le simulateur
  │   simulation_max_days=5, un seul bras
  ▼
 L1 · Multi-jours robuste (S)           ─►  spec 01 : calendrier ouvré, post-traitements par jour,
  │   pause/reprise invariante (Q6),          drainage STM avant pause, cache exact ou coupé,
  │   décideur épinglé côté GAMA,             rejeu des décisions archivées à la reprise (G10),
  │   correction nettoyage LTM                simulation_max_days paramétré par make run
  ▼
 L2 · Événements (M)                    ─►  spec 02 : format étendu (graphe / langue), canal
  │   injection contrôleur → GAMA,            system/evenement, exposition tracée par agent,
  │   dégradation d'offre, retard vécu,       période avant/pendant/après par décision (G9),
  │   choc individuel, placebo, article       recalcul « recalculée:offre » (G4/G6)
  ▼
 L3 · Oracle dans GAMA (S)              ─►  spec 03 : branche « modele » dans le contrôleur,
  │                                           même contrat, renormalisation sur l'offre, sceau
  ▼
 L4 · Collecte (M)                      ─►  spec 04 : souvenirs présentés dans moves.csv,
  │   panel parquet, instantanés LTM,         audit mémoire, exposition, coûts par catégorie,
  │   codage des justifications               export decisions/panel/journal/memoire_audit
  ▼
 L5 · Simulateur de coût (S)            ─►  scripts/AAMAS/simulateur_cout_longitudinal.py
  ▼
 G2 · Répétition générale : palier minimal, 3 bras + placebo, N pilote  ─►  vérifie P3/P4/P7 à blanc
  ▼
 G3 · Pré-enregistrement : gel des prédictions, empreintes, calendrier de campagne (tag git daté)
  ▼
 L6 · Campagne standard (26 j × bras)   ─►  registre, alarmes, reprise quotidienne
  ▼
 L7 · Analyse (M)                       ─►  notebooks/scripts : métriques §6.1, tests §6.2,
  │                                           figures (courbes C, S, δ ; survie ; DiD), rapport HTML
  ▼
 G4 · Décision palier étendu (60 j) et variantes M2…M4 selon résultats et budget
  ▼
 L8 · Rédaction §5.1 du manuscrit, mise à jour experiments.yaml (fiches exp_04e…), BIBLIOGRAPHIE.md
```

Tailles : S = quelques jours, M = une à deux semaines. L1, L2 et L3 sont indépendants après L0 et peuvent être menés en parallèle ; L4 dépend de L2 (exposition) ; G2 dépend de tout.

### 8.1 Protocole opératoire d'une journée de campagne

1. 09:05 Paris (après remise à zéro des quotas Google) : `make run OFFLINE=1 CONT=1 …` reprend ; le registre affiche l'état de chaque bras.
2. La simulation avance jusqu'à 2 h simulées du jour suivant, drainage STM, checkpoint, instantané LTM, puis **pause automatique** si la marge de quota du jour est inférieure au coût estimé du jour suivant (Q11).
3. `make report` ; vérification des `[ALARME]` ; archivage incrémental.
4. Toute interruption (quota, panne, arrêt manuel) est consignée avec instant, cause, durée (Q6) ; la reprise ne redemande **aucune** décision archivée (Q5).

---

## 9. Risques et parades

| Risque | Effet | Parade |
|---|---|---|
| Cache sémantique servant une décision pré-choc après le choc | hystérésis artificiellement nulle ou fausse | cache en correspondance **exacte** ou coupé ; rejeu par archive (Q5) |
| STM perdue à une pause | bras M privé d'observations → sous-estimation | pause seulement après `[drainage] … arrêt sûr` ; test Q6 sur le palier minimal |
| Roulette des fournisseurs | plume différente d'un jour à l'autre, substitution silencieuse | décideur épinglé (Q2/Q3) dans le chemin GAMA ; provider payeur tracé |
| Nettoyage LTM à l'heure réelle | purge de tous les concepts au-delà de 10 000 entrées | correction L1 ; alarme sur purge |
| Effectif exposé trop faible | pas de puissance sur H3-c | stratification §4.3 ; N calibré au pilote ; chocs à exposition choisie (I4) |
| Confusion réaction physique / réaction mémorielle | attribuer à la mémoire ce que l'offre impose | le jour J appartient à P2, l'hystérésis se lit à partir de J+1 seulement ; bras O comme mesure de la contrainte |
| Bras A à température 0 : « vacuité = perfection » | dispersion nulle par construction prise pour une habitude | métrique $C$ sur la distribution émise, tirage seedé par jour, plancher $1 - \sum p^2$ déclaré |
| Effet de la météo réelle | confondu avec le choc | même météo sur tous les bras ; météo dans le modèle mixte ; choc un jour de météo neutre (question Q4) |
| Fin de semaine | chaînes d'activité de semaine un dimanche | jours ouvrés seulement (Q1) |
| Coût des variantes M2…M6 | campagne interminable | palier minimal d'abord ; variantes sur N réduit ; simulateur avant chaque lancement |
| Réflexions génériques auto-réalisatrices (« j'ai l'habitude du métro ») | habitude déclarée sans base | audit mémoire §5.4 : lier chaque réflexion à ses observations ; codage §5.6 |

---

## 10. Livrables

1. Ce plan, validé et amendé (G0).
2. `specs/ticket_041/0{1..4}-*.md` — specs testables par lot ; `questions.md` tenu à jour.
3. Code des lots L1–L5 avec tests ; documentation `docs/arch/memory-stm-ltm.md` (écarts doc/code corrigés), `docs/arch/plateforme-experiences.md` (événements, oracle GAMA), `docs/setup/quickstart.md` (multi-jours, protocole opératoire), changelog.
4. Registre de campagne : un répertoire par bras, empreintes, interruptions, coûts.
5. Rapport d'analyse HTML + notebooks ; figures prêtes pour l'article.
6. Réécriture du §5.1 du manuscrit, fiches `experiments.yaml` (`exp_04e_…` : palier standard, placebo, individuel, variantes), section bibliographique.

---

## 11. Ce qu'un relecteur AAMAS demandera, et la réponse prévue

- *« Votre oracle est aveugle par construction. »* — Il voit l'offre dégradée (renormalisation), comme l'agent ; il ne voit pas le retard vécu, et c'est exactement ce que le plan mesure : la valeur de **l'expérience**, pas de l'information. Le bras M-news sépare les deux.
- *« Vous avez réglé la mémoire pour obtenir l'hystérésis. »* — Bras M = configuration de production antérieure au plan, gelée ; les variantes sont des bras à part, déclarés ; la formule du manuscrit est ajustée après, pas injectée avant.
- *« Un LLM à température 0 n'a pas de variabilité. »* — Le mode est tiré dans la distribution émise, graine par jour ; la métrique principale porte sur la distribution elle-même.
- *« Pas de vérité terrain. »* — Assumé (§0) ; ce qui est testé est l'ordre des bras, la monotonie, la sensibilité, l'ordre de grandeur face à Larcom, van Exel, Loder.
- *« Effet de l'article plutôt que de la mémoire. »* — Le choc I1 principal ne passe par **aucun** texte exogène : seulement le vécu. Le choc individuel I4 n'a même aucune trace dans le graphe.
- *« Résultat dépendant du modèle. »* — Bras M-bis sur une seconde famille au palier minimal (Tier 2, SILICA).
