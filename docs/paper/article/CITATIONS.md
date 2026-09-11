# Actions — vérification une à une des citations de l'introduction

**Objet :** chaque citation de [`chapitres/01_INTRODUCTION_EN.md`](en/01_introduction.md) et [`chapitres/02_RELATED_WORK_EN.md`](en/02_related_work.md) (v0.3) et de son miroir français.
**Mise à jour du 8 septembre 2026 (v0.3) :** à la demande de K. Oberoi, les éléments de contexte de Vu, Gaudou & Oberoi (2025) reviennent en section 1, reformulés phrase à phrase ; leurs cinq références sont réintégrées (A28 à A31, et A19 pour Feng). Leurs PDF manquent dans `etat_de_lart/` : les cases restent ouvertes tant qu'ils n'y sont pas.
**Mise à jour du 10 septembre 2026 (v0.14) :** entrée A33 pour GTA (Lämmer, Colley & Ebel, 2026), repéré après la v0.13 et absent de tout l'état de l'art antérieur. Ses chiffres sont recoupés sur le préprint, pas sur la version ACM : la case reste ouverte.
**Créé le :** 8 septembre 2026, à la suite de la relecture de la v0.1 (voir `archive/INTRODUCTION_EN_v0.1.md`).
**Règle AAMAS rappelée :** les auteurs sont responsables de l'exactitude des citations ; un article aux citations erronées risque un refus d'emblée ([`INSTRUCTIONS_SOUMISSION_AAMAS.md`](SOUMISSION_AAMAS_2027.md), § 4).

**Action ouverte (10 septembre 2026) : vérification manuelle de toutes les citations, à faire en dernier, avant la soumission.** Deux erreurs de bibliographie ont été trouvées ce jour sur des entrées déjà marquées « corrigées » (A12 : un auteur retiré à tort ; A18 : un même auteur sous deux noms). La vérification automatique ne suffit donc pas : chaque entrée du `.bib` est à relire contre la notice de l'éditeur ou d'arXiv — auteurs complets et dans l'ordre, année, support, volume et pages, DOI — et chaque appel de citation du texte contre son entrée. À faire une fois le texte figé, pas avant, pour ne pas recommencer.

## Règle de tenue

Une citation reste dans l'introduction seulement si les quatre conditions sont remplies :

1. **Le PDF est dans `etat_de_lart/`** (ou l'ouvrage est consulté pour les livres sans PDF) ;
2. **L'attribution est exacte** : auteurs dans l'ordre, année, support, identifiant ;
3. **La phrase de l'introduction qui la cite est appuyée par un passage identifié** (page ou section notée ici) ;
4. **La clé BibTeX existe** dans [`references.bib`](../sources/references.bib).

Cocher une case = les quatre conditions vérifiées à la main, pas seulement le fichier ouvert.

---

## A. Citations retenues — à vérifier une à une

### A1. McFadden (1974)
- [ ] PDF : `etat_de_lart/McFadden_1974_Conditional_Logit.pdf`
- Phrase citante : § 2.1, fondement des modèles de choix discrets (RUM, logit conditionnel).
- À pointer : définition du logit conditionnel, p. 105 sq.
- Bib : `mcfadden1974conditional` (présente).

### A2. Ben-Akiva & Lerman (1985)
- [ ] Ouvrage (MIT Press), pas de PDF — consulter l'exemplaire ou la table des matières éditeur.
- Phrase citante : § 2.1, application des choix discrets à la demande de transport.
- À pointer : chapitres sur le logit multinomial et le choix modal.
- Bib : `benakiva1985discrete` (présente).

### A3. Train (2009)
- [ ] PDF : `etat_de_lart/Train_2009_Discrete_Choice_Simulation.pdf`
- Phrase citante : § 2.1, logit mixte et hétérogénéité des goûts par distributions statiques.
- À pointer : chap. 6 (Mixed Logit).
- Bib : `train2009discrete` (présente). **La v0.1 citait « Train, 2002 » : corrigé en 2009.**

### A4. Adam & Gaudou (2025)
- [ ] PDF : `etat_de_lart/Gaudou_2025_Enquete_Perceptions_Mobilite.pdf`
- Phrase citante : § 2.1, biais de perception liés à l'habitude ; 650 répondants ; « convinced car drivers tend to underestimate the price of the car ».
- À pointer : § Introduction (biais de perception) et § Survey (650 réponses). Vérifier que la formulation nuancée « chez les automobilistes habitués » correspond au texte.
- Bib : **créée le 8 septembre 2026** (`adam2025survey`).

### A5. Park et al. (2023)
- [ ] PDF : `etat_de_lart/Park_2023_Generative_Agents.pdf`
- Phrase citante : § 2.2, architecture d'agents génératifs avec mémoire épisodique et réflexion ; § 4 (C3), registre de mémoire court terme.
- À pointer : § 4 (architecture : memory stream, reflection, planning).
- Bib : `park2023generative` (présente).

### A6. Chopra et al. (2024)
- [ ] PDF : `etat_de_lart/Limits_of_Agency_ABM_2024.pdf`
- Phrase citante : § 2.2, coût des agents LLM à l'échelle d'une population et archétypes comme réponse.
- À pointer : § sur les LLM archetypes et le coût d'inférence.
- Bib : **créée le 8 septembre 2026** (`chopra2024limits`, arXiv:2409.10568).

### A7. Liu, Yang & Yin (2024)
- [ ] PDF : `etat_de_lart/Toward_LLM_ABM_Transportation_2024.pdf` (arXiv:2412.06681, v2 avril 2025)
- Phrases citantes : § 1 (v0.4), les modèles à base d'agents exigent des données locales étendues pour leur calage, frein à leur adoption, et les règles fixes limitent l'adaptation ; § 2.2, cadre conceptuel d'ABM de transport à agents LLM ; hybridation proposée comme stratégie d'intégration à court terme.
- À pointer : § 1 Introduction (« agent-based models often require extensive local data for calibration, posing a significant obstacle to their widespread adoption ») ; abstract (« hybrid modeling as a near-term integration strategy ») et section de discussion correspondante.
- Bib : **créée le 8 septembre 2026** (`liu2024toward`).

### A8. Bougie & Watanabe (2025) — CitySim
- [ ] PDF : `etat_de_lart/CitySim_Urban_Behaviors_2025.pdf` (arXiv:2506.21805)
- Phrase citante : § 2.2, simulation urbaine à grande échelle d'agents LLM ; ce contre quoi CitySim valide, et ce qu'il ne confronte pas (répartition modale).
- **Vérifié le 8 septembre 2026 sur le PDF.** § 4.1 : emploi du temps comparé à l'enquête nationale japonaise 2021 (Statistics Bureau of Japan, « Survey on time use and leisure activities »). § 4.3 : nombre de déplacements par heure comparé à un jeu propriétaire à l'échelle de la ville. § 4.6 : densités de foule à Shibuya comparées à des cartes réelles. § 4.2 : plausibilité des routines jugée par GPT‑4o (naturalness, coherence, plausibility, taux de victoire par paires). § 3.2.3 : un module « Vehicle Selection » estime le mode de chaque déplacement, mais aucune expérience ne confronte la répartition modale simulée à une répartition observée ; aucune enquête déplacements n'est citée. Table 1 : prédiction de cinq classes de bien‑être sur une enquête propriétaire de 1 200 réponses, macro‑F1 CitySim 0,36 ± 0,02 contre GBDT 0,45 ± 0,04 — le modèle tabulaire l'emporte.
- **Corrigé en v0.6** (REMARQUES 2.2) : la phrase dit ce que CitySim valide et contre quoi, mentionne la limite de reproductibilité déclarée par les auteurs (§ 6), et qu'aucune expérience ne confronte la répartition modale à une observation.
- Bib : **créée le 8 septembre 2026** (`bougie2025citysim`).

### A9. Alves et al. (2026)
- [ ] PDF : `etat_de_lart/Evaluating_LLMs_ABM_Urban_Mobility_2026.pdf` (arXiv:2607.02716)
- Phrases citantes : § 1 (v0.4), les approches à règles reposent sur des heuristiques fixes qui limitent l'adaptation ; § 2.2, GAMA + module LLM externe décidant du re-routage, mémoire persistante, scénarios de blocage ; aucune vérité terrain d'enquête, aucune métrique distributionnelle.
- À pointer : abstract et section Results — confirmer l'absence de comparaison à des données humaines.
- Bib : **créée le 8 septembre 2026** (`alves2026evaluating`).

### A10. Vu, Gaudou & Oberoi (2025)
- [ ] PDF : `etat_de_lart/Vu_2025_Generative_Agents_Toulouse.pdf` (arXiv:2510.19497)
- Phrase citante : § 1, article de plateforme sur lequel le présent travail s'appuie (architecture GAMA + agents génératifs + OTP, Toulouse).
- À pointer : § architecture logicielle.
- Bib : **créée le 8 septembre 2026** (`vu2025modeling`).
- **Note :** la v0.1 reprenait mot pour mot les trois premiers paragraphes de cet article. La v0.2 les réécrit ; la v0.3 rétablit leurs idées et leurs références, reformulées phrase à phrase. **Contrôle du 8 septembre 2026 :** fenêtres de mots consécutifs communes avec l'article de Vu et al. — v0.1 : 215 fenêtres de 10 mots ; v0.2 : 0 de 10, 0 de 7 ; v0.3 : 0 de 10, 3 de 7 (« detailed trajectory and itinerary datasets which are », « public transit, walking, cycling and shared services »), 16 de 5. v0.4 (section 1 rapprochée de la v0.1 à la demande du tuteur) : 0 fenêtre de 10 mots, 3 de 8 (« journeys tailored to individual preferences Smith et al », « public transit walking cycling and shared services are »), 7 de 7. Les recouvrements restants sont des syntagmes techniques ou des appels de citation, pas des phrases ; à relire une dernière fois avant soumission.

### A11. Argyle et al. (2023)
- [ ] PDF : `etat_de_lart/Argyle_2023_OutOfOneMany.pdf` (arXiv:2209.06899 ; *Political Analysis* 31(3), 2023)
- Phrase citante : § 2.3, « silicon sampling » : personas conditionnés par attributs sociodémographiques.
- À pointer : abstract et § 2 (algorithmic fidelity).
- Bib : **créée le 8 septembre 2026** (`argyle2023outofone`). **La v0.1 citait 2022 : corrigé en 2023.**

### A12. Meister, Guestrin & Hashimoto (2024)
- [ ] PDF : `etat_de_lart/Meister_2024_Benchmarking_Distributional_Alignment.pdf` (arXiv:2411.05403)
- Phrases citantes : § 2.3, benchmark d'alignement distributionnel ; § 4 (C1), une distribution verbalisée en JSON s'aligne mieux qu'un échantillonnage, un modèle « connaît » une distribution sans savoir en tirer.
- À pointer : abstract, § 3 (Distribution Expression Methods), résultat « Verbalize » vs « Sequence » vs logprobs.
- Bib : **créée le 8 septembre 2026** (`meister2024benchmarking`). La passe du 8 septembre avait ramené la citation à deux auteurs ; **c'était une erreur** : la notice arXiv 2411.05403 (vérifiée le 10 septembre 2026) donne Nicole Meister, Carlos Guestrin **et Tatsunori Hashimoto**. Bib et texte rétablis en « Meister et al. » (v0.17 du chapitre 2).

### A13. Kambhatla et al. (2025)
- [ ] PDF : `etat_de_lart/Supervision_2025_Distributional_Alignment.pdf` (arXiv:2507.00439)
- Phrase citante : § 2.3, une supervision simple améliore l'alignement distributionnel sur des groupes de population.
- À pointer : abstract et tableau principal.
- Bib : **créée le 8 septembre 2026** (`kambhatla2025improving`).

### A14. Huang, Li & Shao (2025)
- [ ] PDF : `etat_de_lart/DistShift_2025_Survey_Distributions.pdf` (arXiv:2510.21977)
- Phrase citante : § 2.3, l'alignement du décalage de distribution aide les LLM à simuler des distributions de réponses d'enquête.
- À pointer : abstract et section méthode.
- Bib : **créée le 8 septembre 2026** (`huang2025distribution`).

### A15. Nguyen, Tschiatschek & Singla (2025)
- [ ] PDF : `etat_de_lart/Prompt_Optimization_Diverse_Populations_2025.pdf` (arXiv:2510.07064)
- Phrase citante : § 2.3, un ensemble d'agents conditionnés par démonstrations pour couvrir la diversité d'une population.
- À pointer : abstract et § 3.
- Bib : **créée le 8 septembre 2026** (`nguyen2025prompt`).

### A16. Bin Tareaf (2026) — SILICA
- [ ] PDF : `etat_de_lart/BinTareaf_2026_SILICA_Benchmark.pdf` (arXiv:2608.28182)
- Phrases citantes : § 3, 9 115 runs, douze modèles open-weight, cinq environnements de jeux économiques, aucune conclusion « transferable » ; certification exploratory / robust / transferable ; limites déclarées (pas de modèle frontière, ancrages agrégés WEIRD, auteur unique).
- À pointer : § 3.8 Certification ; § 5.4 « What a Tier-3 result would require » ; § 5.5 « Limits of this evidence ».
- Bib : `bintareaf2026silica` — **corrigé le 8 septembre 2026 : auteur unique, identifiant arXiv ajouté.**

### A17. Flint Ashery, Aiello & Baronchelli (2025)
- [ ] PDF : `etat_de_lart/Baronchelli_2025_Emergent_Conventions.pdf`
- Phrases citantes : § 2.3 et § 3, émergence de conventions et biais collectifs ; les auteurs déclarent ne pas traiter les LLM comme substituts de participants humains.
- À pointer : p. 1 (« our work does not treat LLMs as proxies for human participants ») ; footnote de première page pour le support.
- Bib : `baronchelli2025emergent` — **corrigé le 8 septembre 2026 : premier auteur Flint Ashery ; support *Science Advances* 11(20), eadu9368 (le bib disait 11(8), eadp3456).**

### A18. Flint Ashery, Aiello, Pastor-Satorras & Baronchelli (2025)
- [ ] PDF : `etat_de_lart/Baronchelli_2026_Group_Size_Effects.pdf` (arXiv:2510.22422, octobre 2025)
- Phrase citante : § 2.3, la taille du groupe modifie les dynamiques collectives de façon non linéaire et dépendante du modèle.
- À pointer : abstract (« group size affects the dynamics in a non-linear way, revealing model-dependent dynamical regimes »).
- Bib : `baronchelli2026groupsize` — **corrigé : premier auteur Flint, cité 2025 sur arXiv ; la publication PNAS 123(12) annoncée par les versions antérieures n'est pas vérifiable depuis le PDF archivé : à confirmer avant de citer la version journal.** La randomisation de l'ordre des options est désormais attribuée à SILICA (A16), qui la teste explicitement.
- **10 septembre 2026 :** premier auteur harmonisé en **Flint Ashery** dans le bib et le texte (v0.17 du chapitre 2). La prépublication arXiv 2510.22422 imprime « Ariel Flint », l'article *Science Advances* du même auteur (A17) « Ariel Flint Ashery » ; une personne, un nom dans la liste de références. Année 2025 conservée (prépublication d'octobre 2025) ; la publication PNAS annoncée par `sources/etat_de_lart/README.md` reste **non vérifiée**.

### A19. Feng, Du, Zhao & Li (2024) — AgentMove
- [ ] PDF : `etat_de_lart/AgentMove_Next_Location_Prediction_2024.pdf` (arXiv:2408.13986)
- Phrase citante : § 1 (v0.4), les jeux de trajectoires n'existent que pour un nombre restreint de grandes métropoles, Tokyo par exemple, et leur couverture est très inégale d'une ville à l'autre.
- À pointer : § Experiments, douze villes évaluées ; Figure 4, précision plus élevée à Tokyo, Paris et Sydney qu'au Cap et à Nairobi (« significant differences in the accuracy … across cities »). Vérifié le 8 septembre 2026 sur le PDF : Tokyo y figure bien.
- Bib : **créée le 8 septembre 2026** (`feng2024agentmove`).

### A20. Sécheresse, Guilbert-Ly & Villedieu de Torcy (2025) — GAAPO
- [ ] PDF : `etat_de_lart/Secheresse_2025_GAAPO.pdf` (arXiv:2504.07157)
- Phrase citante : § 2.3, optimisation génétique de prompt (famille du calibreur du projet).
- À pointer : abstract.
- Bib : **créée le 8 septembre 2026** (`secheresse2025gaapo`).

### A21. Guo et al. (2023) — EvoPrompt
- [ ] PDF : `etat_de_lart/Guo_2023_EvoPrompt.pdf` (arXiv:2309.08532)
- Phrase citante : § 2.3, optimisation évolutionnaire de prompts.
- À pointer : abstract.
- Bib : **créée le 8 septembre 2026** (`guo2023evoprompt`).

### A22. Pryzant et al. (2023) — ProTeGi
- [ ] PDF : `etat_de_lart/Pryzant_2023_ProTeGi.pdf` (arXiv:2305.03495)
- Phrase citante : § 2.3, optimisation automatique de prompt visant l'exactitude d'une tâche.
- À pointer : abstract.
- Bib : **créée le 8 septembre 2026** (`pryzant2023automatic`).

### A23. Opsahl-Ong et al. (2024) — MIPRO
- [ ] PDF : `etat_de_lart/OpsahlOng_2024_DSPy_MIPROv2.pdf` (arXiv:2406.11695)
- Phrase citante : § 2.3, idem.
- À pointer : abstract.
- Bib : **créée le 8 septembre 2026** (`opsahlong2024optimizing`).

### A24. Ke et al. (2017) — LightGBM
- [ ] PDF : `etat_de_lart/Ke_2017_LightGBM.pdf`
- Phrase citante : § 4 C1 (v0.7), définition de l'oracle supervisé : un modèle LightGBM ajusté sur les microdonnées de l'enquête, plafond de référence.
- Bib : `ke2017lightgbm` (présente).

### A25. Hörl & Balać (2021) — eqasim
- [ ] Pas de PDF dans `etat_de_lart/` — télécharger (TRR 2675(11)) ou consulter.
- Phrase citante : § 4 (C1), vivier de population synthétique.
- Bib : `horl2021eqasim` (présente).

### A26. Taillandier et al. (2019) — GAMA
- [ ] Pas de PDF dans `etat_de_lart/` — HAL hal-02058315.
- Phrase citante : **plus citée dans l'introduction depuis la v0.6** (décision REMARQUES 1.5) ; à citer une fois en section méthodes, à la description de la plateforme.
- Bib : `taillandier2019gama` (présente, conservée). **Note :** la liste d'auteurs de [`BIBLIOGRAPHIE.md`](../sources/BIBLIOGRAPHIE.md) § 3 contient un nom corrompu (« Pドラ ») : à corriger dans ce fichier.

### A27. Tisséo Collectivités & AUAT (2023) — EMC² 2023
- [ ] Rapport final (68 p., mai 2024) et microdonnées ProGEDO lil-1750.
- Phrases citantes : § 1 et § 4, enquête certifiée Cerema, environ 16 000 répondants, 453 communes ; cibles de parts modales.
- À pointer : p. 10, 11, 21 du rapport (marges) ; effectif de l'enquête.
- Bib : `tisseo2023emc2` (présente).

### A28. Smith, Beckman & Baggerly (1995) — TRANSIMS
- [ ] **PDF absent de `etat_de_lart/`** — rapport technique LANL 1995 à récupérer. Retenue à la demande du tuteur (v0.3).
- Phrase citante : § 1, systèmes de transport personnalisés et multimodaux intégrant TC, marche, vélo et services partagés.
- À pointer : présentation de TRANSIMS comme simulation individu-centrée.
- Bib : `smith1995transims` (créée le 8 septembre 2026, d'après la bibliographie de Vu et al.).

### A29. Grignard et al. (2018)
- [ ] **PDF absent de `etat_de_lart/`** — le README de l'état de l'art le liste parmi les téléchargements manuels (ResearchGate / Springer, doi 10.1007/978-3-319-96661-8_29). Retenue à la demande du tuteur (v0.3).
- Phrase citante : § 1, les choix de mobilité dépendent du profil socio-économique, des contraintes d'accessibilité et de l'expérience vécue.
- À pointer : section motivant l'ABM par l'hétérogénéité des profils.
- Bib : `grignard2018impact` (créée le 8 septembre 2026).

### A30. Oberoi (2024)
- [ ] **PDF absent de `etat_de_lart/`** — VEHITS 2024, doi 10.5220/0012687100003702. Retenue à la demande du tuteur (v0.3).
- Phrase citante : § 1, la personnalisation en MaaS exige de traiter l'hétérogénéité des usagers (préférences, contextes, besoins d'accessibilité), verrou pour des modèles réalistes.
- À pointer : passage sur l'hétérogénéité des usagers et ses conséquences pour la modélisation.
- Bib : `oberoi2024personalisation` (créée le 8 septembre 2026).

### A31. Fourez et al. (2025)
- [ ] **PDF absent de `etat_de_lart/`** — Transportation Research Procedia 82, doi 10.1016/j.trpro.2024.12.083. Retenue à la demande du tuteur (v0.3).
- Phrase citante : § 1, rareté des jeux de trajectoires et d'itinéraires détaillés.
- À pointer : introduction (motivation par la rareté des données de trajectoires annotées).
- Bib : `fourez2025transport` (créée le 8 septembre 2026).

### A32. Horni, Nagel & Axhausen (2016) — MATSim
- [ ] Ouvrage Ubiquity Press (doi 10.5334/baw), pas de PDF — le README de l'état de l'art le liste parmi les téléchargements manuels.
- Phrase citante : § 1, aux côtés de Smith et al. 1995, simulation multi-agents de transport centrée sur l'individu.
- **Attribution :** Vu et al. citent « W Axhausen et al., 2016 » ; l'ordre des éditeurs de l'ouvrage est Horni, Nagel & Axhausen, et c'est ainsi que la v0.3 le cite.
- Bib : `horni2016matsim` (présente).

### A33. Lämmer, Colley & Ebel (2026) — GTA

- [ ] **PDF absent de `etat_de_lart/`** — CHI 2026, article court, doi 10.1145/3772318.3790772 ; préprint arXiv:2601.16778 (v1 du 23 janvier 2026, v2 du 27 janvier 2026).
- Phrase citante : § 1, la mesure existe déjà mais sans référence modélisée ; § 2.2, description du système et de son comparateur interrégional.
- À pointer : § 4.1 (échantillon de 35 769 agents), tableau 2 (Berlin simulation 4,07 / 6,07 / 6,12 / 5,42 ; Hambourg 1,99 / 1,42), tableau 3 (ablations 5,42 à 8,23), § 6 (mémoire multi-jours donnée comme travail futur).
- **Recoupement :** chiffres extraits du texte intégral HTML arXiv v2 le 10 septembre 2026, hors du modèle de lecture, par recherche littérale sur la page. **À revérifier sur le PDF ACM avant soumission** — c'est la version publiée qui fait foi, et la comparaison v1/v2 n'a pas été faite.
- **Attribution :** trois auteurs, dans l'ordre Lämmer, Colley, Ebel. Le tréma de « Lämmer » est encodé `{\"a}` dans le bib.
- Bib : `lammer2026gta` (créée le 10 septembre 2026).

---

## B. Entrées BibTeX créées (récapitulatif)

Créées le 8 septembre 2026 ; les listes d'auteurs de A21, A22 et A23 sont à confirmer sur le PDF (note dans le bib).

- [x] `adam2025survey` — A4 — créée dans references.bib le 8 septembre 2026
- [x] `chopra2024limits` — A6 — créée dans references.bib le 8 septembre 2026
- [x] `liu2024toward` — A7 — créée dans references.bib le 8 septembre 2026
- [x] `bougie2025citysim` — A8 — créée dans references.bib le 8 septembre 2026
- [x] `alves2026evaluating` — A9 — créée dans references.bib le 8 septembre 2026
- [x] `vu2025modeling` — A10 — créée dans references.bib le 8 septembre 2026
- [x] `argyle2023outofone` — A11 — créée dans references.bib le 8 septembre 2026
- [x] `meister2024benchmarking` — A12 — créée dans references.bib le 8 septembre 2026
- [x] `kambhatla2025improving` — A13 — créée dans references.bib le 8 septembre 2026
- [x] `huang2025distribution` — A14 — créée dans references.bib le 8 septembre 2026
- [x] `nguyen2025prompt` — A15 — créée dans references.bib le 8 septembre 2026
- [x] `feng2024agentmove` — A19 — créée dans references.bib le 8 septembre 2026
- [x] `secheresse2025gaapo` — A20 — créée dans references.bib le 8 septembre 2026
- [x] `guo2023evoprompt` — A21 — créée dans references.bib le 8 septembre 2026
- [x] `pryzant2023automatic` — A22 — créée dans references.bib le 8 septembre 2026
- [x] `opsahlong2024optimizing` — A23 — créée dans references.bib le 8 septembre 2026
- [x] `smith1995transims` — A28 — créée le 8 septembre 2026 (v0.3)
- [x] `grignard2018impact` — A29 — créée le 8 septembre 2026 (v0.3)
- [x] `oberoi2024personalisation` — A30 — créée le 8 septembre 2026 (v0.3)
- [x] `fourez2025transport` — A31 — créée le 8 septembre 2026 (v0.3)
- [x] `lammer2026gta` — A33 — créée dans references.bib le 10 septembre 2026 (v0.14)

---

## C. Citations retirées de la v0.1 et motif

- [ ] **Smith et al. (1995)** — retirée en v0.2 (héritée du paragraphe repris de Vu et al.), **réintroduite en v0.3** à la demande du tuteur : voir A28.
- [ ] **Axhausen et al. (2016)** — retirée en v0.2, **réintroduite en v0.3** sous l'attribution correcte Horni, Nagel & Axhausen : voir A32.
- [ ] **Grignard et al. (2018)** — retirée en v0.2, **réintroduite en v0.3** : voir A29.
- [ ] **Oberoi (2024)** — retirée en v0.2, **réintroduite en v0.3** : voir A30.
- [ ] **Fourez et al. (2025)** — retirée en v0.2, **réintroduite en v0.3** : voir A31.
- [x] **Feng et al. (2025)** — aucune trace dans le dépôt ; seul AgentMove 2024 existe (A19).
- [x] **Sameen et al. (2025) [SAPA]** — aucune trace dans le dépôt ; existence non vérifiable.
- [x] **Chu & Guo (2023)** — aucune trace dans le dépôt.
- [x] **Choi et al. (2026)** — aucune trace dans le dépôt ; existence non vérifiable.
- [x] **Łajewska et al. (2026)** — aucune trace dans le dépôt ; existence non vérifiable.
- [x] **Baronchelli (2026), « A useful stress test… »** — post LinkedIn ; ne peut pas porter le cadre épistémologique. La dichotomie est désormais énoncée en notre nom, appuyée sur A17. **`baronchelli2026stresstest` supprimé du bib le 8 septembre 2026** ; à réintroduire seulement sous une forme publiée.
- [x] **Zhou et al. (2022) — APE** et **Yang et al. (2023) — OPRO** — PDF présents mais non nécessaires à la phrase unique sur l'optimisation de prompt ; réintroduisibles.
- [x] **Train (2002)** — remplacé par Train (2009), A3.
- [x] **Argyle et al. (2022)** — remplacé par Argyle et al. (2023), A11.
- [x] **Bin Tareaf et al.** → **Bin Tareaf (2026)**, auteur unique, A16.
- [x] **Baronchelli (2025, 2026)** → **Flint Ashery et al. (2025)** et **Flint et al. (2025)**, A17 et A18.

---

## D. Vérifications complémentaires sur les chiffres de l'introduction

Chaque chiffre conservé dans la v0.2 doit se recalculer depuis un fichier du dépôt sur la référence actuelle. Sources déclarées en commentaire HTML dans le texte.

- [ ] Population scellée : 1 000 personas, sceau 1 du 2 septembre 2026, sha256 `f67b0777…` — `data/population/population_1000_AAMAS/MANIFEST.yaml`.
- [ ] Vivier eqasim : 5 063 personnes — même manifeste.
- [ ] Contrôle démographique : 6 marges conformes, 2 non mesurables — `CONTROLE.md` du même dossier.
- [ ] Déplacements du jour évalué : 2 693 planifiés, 2 645 exploitables — `compteurs.json` des exécutions du 7 septembre 2026.
- [ ] Jeu de test scellé de l'oracle : 13 045 trajets, découpage par ménage — `scripts/progedo_logit/mode_choice_policy_metrics.json` (`test.n_rows`).
- [ ] Contrat de 21 variables, `spec_version 2` — `scripts/progedo_logit/feature_spec.json`.
- [ ] Jusqu'à six itinéraires présentés — `max_candidats: 6` dans `experience.yaml` des expériences jouées.
- [x] Corpus de 30 articles, 7 classés « éliminer » — plus mentionné dans l'introduction depuis la v0.7 (cinq articles, choisis avant tout appel) ; reste vrai pour l'annexe.
- [ ] Enquête EMC² 2023 : environ 16 000 répondants, 453 communes — rapport AUAT/CEREMA.
- [ ] Tout autre chiffre porte un tag **[xx.y | exp_id]** jusqu'à mesure sur le substrat scellé.

---

---

## E. Clés BibTeX

Le schéma de clés de l'exemple AAMAS (initiales + année, `WoJe95`) a été essayé le 8 septembre 2026 puis abandonné le même jour à la demande de l'auteur : les clés descriptives `auteurAnnéeMot` (`smith1995transims`, `horni2016matsim`) sont conservées. Le format des entrées reste celui de l'exemple AAMAS : valeurs entre accolades, seuls les champs renseignés sont écrits, acronymes des titres protégés.
