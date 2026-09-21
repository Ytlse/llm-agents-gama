# Actions — vérification une à une des citations de l'introduction

**Objet :** chaque citation de [`chapitres/01_INTRODUCTION_EN.md`](en/01_introduction.md) et [`chapitres/02_RELATED_WORK_EN.md`](en/02_related_work.md) (v0.3) et de son miroir français.
**Mise à jour du 8 septembre 2026 (v0.3) :** à la demande de K. Oberoi, les éléments de contexte de Vu, Gaudou & Oberoi (2025) reviennent en section 1, reformulés phrase à phrase ; leurs cinq références sont réintégrées (A28 à A31, et A19 pour Feng). Leurs PDF manquent dans `etat_de_lart/` : les cases restent ouvertes tant qu'ils n'y sont pas.
**Mise à jour du 17 septembre 2026 (v0.18) :** A32 (MATSim) retrouve une phrase citante. L'entrée la donnait en § 1 ; aucune phrase des chapitres 1 et 2 ne la citait plus depuis que l'état de l'art a quitté l'introduction, et la référence restait au bib sans appel. Le paragraphe d'ouverture du § 2.2 la cite désormais, aux côtés de A5 (Park et al.), dont l'entrée annonçait déjà le § 2.2. Aucune citation nouvelle : les onze références proposées par une refonte du chapitre (Simon, Kahneman & Tversky, McKelvey & Palfrey, Wardrop, Rosenthal, Hong, Li, Gao, Sun, Ge) n'ont pas été retenues, faute de PDF au dépôt et de phrase du protocole qui les emploie.
**Mise à jour du 10 septembre 2026 (v0.14) :** entrée A33 pour GTA (Lämmer, Colley & Ebel, 2026), repéré après la v0.13 et absent de tout l'état de l'art antérieur. Ses chiffres sont recoupés sur le préprint, pas sur la version ACM : la case reste ouverte.
**Mise à jour du 21 septembre 2026 :** entrées A34 à A39, les cinq références de langue d'inférence citées par le § 4.1 et le § 8.6 (ticket 074). Toutes ont leur PDF au dépôt, dans `docs/paper/mémoire/` et non dans `etat_de_lart/` : c'est le corpus reconstitué du ticket 072. Les auteurs sont relevés sur les premières pages des PDF, les champs `authors` des métadonnées JSON de ce dossier étant vides. Trois points restent à trancher avant soumission et sont notés entrée par entrée : la lecture du troisième auteur de Bazoge et al., l'année de Bulté & Rigouts Terryn, et les deux caractères CJK du titre de Liu et al. que pdflatex ne compose pas.
**Créé le :** 8 septembre 2026, à la suite de la relecture de la v0.1 (voir `archive/INTRODUCTION_EN_v0.1.md`).
**Règle AAMAS rappelée :** les auteurs sont responsables de l'exactitude des citations ; un article aux citations erronées risque un refus d'emblée ([`INSTRUCTIONS_SOUMISSION_AAMAS.md`](SOUMISSION_AAMAS_2027.md), § 4).

**Action ouverte (10 septembre 2026) : vérification manuelle de toutes les citations, à faire en dernier, avant la soumission.** Deux erreurs de bibliographie ont été trouvées ce jour sur des entrées déjà marquées « corrigées » (A12 : un auteur retiré à tort ; A18 : un même auteur sous deux noms). La vérification automatique ne suffit donc pas : chaque entrée du `.bib` est à relire contre la notice de l'éditeur ou d'arXiv — auteurs complets et dans l'ordre, année, support, volume et pages, DOI — et chaque appel de citation du texte contre son entrée. À faire une fois le texte figé, pas avant, pour ne pas recommencer.

## Règle de tenue

Une citation reste dans l'introduction seulement si les quatre conditions sont remplies :

1. **Le PDF est dans `etat_de_lart/`** (ou l'ouvrage est consulté pour les livres sans PDF) ;
2. **L'attribution est exacte** : auteurs dans l'ordre, année, support, identifiant ;
3. **La phrase de l'introduction qui la cite est appuyée par un passage identifié** (page ou section notée ici) ;
4. **La clé BibTeX existe** dans [`sample.bib`](../sources/sample.bib), celle que le template
   LaTeX appelle (`\bibliography{sample}`). Le fichier `sample.bib` que cette condition
   nommait jusqu'au 21 septembre 2026 avait été supprimé au commit `8c1871a` : la porte
   désignait un fichier absent, donc ne filtrait plus rien.

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
- Phrase citante : § 4 C1 (v0.7), définition des références tabulaires supervisées, dont un modèle LightGBM ajusté sur les microdonnées de l'enquête.
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
- Bib : `tisseo2023emc2` (présente, complétée le 11 septembre 2026 d'une `note` : microdonnées diffusées par Quetelet-Progedo-Diffusion, convention `lil-1750`).
- **Deux objets distincts, deux citations.** Le **rapport publié** (marges, parts modales) est citable sans réserve ; les **microdonnées** relèvent de la convention `lil-1750` et se citent selon son modèle annexé → entrée `progedo2023emc2microdata` et A34.

### A34. Microdonnées EMC² 2023 (Quetelet-Progedo-Diffusion, lil-1750)
- [ ] **Modèle de citation à recopier depuis l'annexe de la convention** — le libellé écrit aujourd'hui dans l'Annexe G est provisoire et marqué comme tel. Tant que cette case n'est pas cochée, aucune version n'est envoyée au diffuseur.
- Phrases citantes : § 4.7 (conditions d'accès et conséquences sur le matériel supplémentaire), Annexe G, et partout où un chiffre est ajusté sur microdonnées (logit, références tabulaires, marges recalculées).
- Engagements associés (usage recherche, non-cession, information du diffuseur) : [`../sources/ENGAGEMENT_DONNEES_EMC2.md`](../sources/ENGAGEMENT_DONNEES_EMC2.md).
- Bib : `progedo2023emc2microdata` (créée le 11 septembre 2026).

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
- Phrase citante : § 2.2, ouverture — boucle co-évolutive hors ligne, programmes notés par une fonction écrite à l'avance, agent qui ne délibère pas. **Déplacée le 17 septembre 2026 (v0.18) :** l'entrée la donnait en § 1 aux côtés de Smith et al. 1995, mais la phrase avait disparu des deux chapitres quand l'état de l'art est devenu le chapitre 2.
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

### A34. Qi et al. (2025) — langue de la trace de raisonnement

- [x] PDF : `docs/paper/mémoire/22_When_Models_Reason_in_Your_Language_Controlling_Thinking_Language_Come.pdf` (corpus du ticket 072, hors `etat_de_lart/`).
- Phrase citante : § 4.1, premier des quatre résultats qui appuient l'exécution en anglais.
- À pointer : titre et résumé — contraindre la langue de la trace coûte de l'exactitude.
- **Attribution :** six auteurs relevés sur la première page du PDF, dans l'ordre Qi, Chen, Xiong, Fernández, Bitterman, Bisazza. Findings of EMNLP 2025, doi 10.18653/v1/2025.findings-emnlp.1103, arXiv:2505.22888v2.
- Bib : `qi2025thinking` (créée le 21 septembre 2026).

---

### A35. Liu et al. (2025) — biais de langue locale en recommandation agentique

- [x] PDF : `docs/paper/mémoire/04_7_Points_to_Tsinghua_but_10_Points_to__Assessing_Large_Language_Models.pdf`.
- Phrase citante : § 4.1, deuxième résultat.
- À pointer : résumé et section de résultats — prévalence du biais de langue locale, aggravé par le raisonnement explicite.
- **Attribution :** quatre auteurs relevés sur la première page, dans l'ordre Liu, Wang, Cheng, Kurohashi. Le premier auteur est **Qianying Liu**, homonymie à éviter avec les deux autres Liu du corpus. Findings of ACL 2025, doi 10.18653/v1/2025.findings-acl.1355, arXiv:2502.17945v2.
- **Point de compilation :** le titre publié porte deux caractères CJK (清华) que pdflatex ne compose pas. Le `note` de l'entrée le signale ; à trancher avant soumission (substitution ou changement de moteur).
- Bib : `liu2025agenticbias` (créée le 21 septembre 2026).

---

### A36. Bazoge et al. (2026) — anglais contre français, raisonnement diagnostique

- [x] PDF : `docs/paper/mémoire/08_Prompting_language_influences_diagnostic_reasoning_and_accuracy_of_lar.pdf`.
- Phrase citante : § 4.1, troisième résultat, seul du corpus à comparer directement l'anglais et le français.
- À pointer : résumé — 180 vignettes, 16 spécialités, 5 modèles, 2 médecins évaluateurs, échelle 18 points, écart moyen 0,37 à 0,91 avec p ajusté < 0,05, o3 sans effet de langue.
- **Attribution à confirmer :** la première page présente les auteurs sur deux lignes sans séparateur. Lecture retenue : Adrien Bazoge, Josselin Corvellec, Sofiane Djillali Sid-Ahmed, Pierre-Antoine Gourraud — le troisième nom pouvant se lire autrement. **À recouper sur la notice arXiv avant soumission.** Préprint arXiv:2605.19173v1, doi 10.48550/arXiv.2605.19173.
- Bib : `bazoge2026prompting` (créée le 21 septembre 2026).

---

### A37. Bulté & Rigouts Terryn (2026) — langue du prompt contre cadrage culturel explicite

- [x] PDF : `docs/paper/mémoire/09_LLMs_and_Cultural_Values_the_Impact_of_Prompt_Language_and_Explicit_Cu.pdf`.
- Phrase citante : § 4.1, quatrième résultat — l'ancrage territorial ne se perd pas à la traduction.
- À pointer : résumé et conclusion sur l'efficacité du cadrage culturel explicite formulé en anglais.
- **Attribution :** deux auteurs, contribution égale, dans l'ordre Bulté, Rigouts Terryn. Le patronyme du second est en deux mots, « Rigouts Terryn », et se saisit entier comme nom de famille dans le bib.
- **Année à confirmer :** le PDF est un préprint arXiv:2511.03980v1 daté du 6 novembre **2025** ; le doi 10.1162/COLI.a.583 est celui de *Computational Linguistics*. L'entrée porte 2026 comme le ticket 074, le `note` signale l'écart. **À trancher sur la notice éditeur avant soumission.**
- Bib : `bulte2026cultural` (créée le 21 septembre 2026).

---

### A38. Ying et al. (2025) — synergie langue-culture

- [x] PDF : `docs/paper/mémoire/14_Disentangling_Language_and_Culture_for_Evaluating_Multilingual_Large_L.pdf`.
- Phrase citante : § 4.1, première des deux réserves — bénéfice auquel l'exécution en anglais renonce.
- À pointer : résumé, phénomène de « Cultural-Linguistic Synergy » et sondage d'interprétabilité sur les neurones activés.
- **Attribution :** six auteurs relevés sur la première page, dans l'ordre Ying, Tang, Zhao, Cao, Rong, Zhang. ACL 2025 (volume long), doi 10.18653/v1/2025.acl-long.1082, arXiv:2505.24635.
- Bib : `ying2025disentangling` (créée le 21 septembre 2026).

---

### A39. Soegeng et al. (2026) — biais occidental induit par l'anglais

- [x] PDF : `docs/paper/mémoire/11_Cross-Lingual_Consensus_Aligning_Multilingual_Cultural_Knowledge_via_M.pdf`.
- Phrase citante : § 4.1, seconde réserve, **et § 8.6**, où elle porte la limite déclarée du chapitre 8.
- À pointer : introduction — la performance est la meilleure en anglais, mais la connaissance culturelle présente dans les représentations en langue locale y est mal récupérée.
- **Attribution :** trois auteurs relevés sur la première page, dans l'ordre Soegeng, Sutanto, Nguyen. Préprint arXiv:2605.22137v2, doi 10.48550/arXiv.2605.22137.
- Bib : `soegeng2026crosslingual` (créée le 21 septembre 2026).

---

### Écartée — Ananthram et al. (2025)

Le § 1.3 du [ticket 074](../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) la compte parmi les réserves à énoncer : le français étant bien représenté au pré-entraînement, le coût de l'exécution en français restait faible. Vérification sur le PDF (`docs/paper/mémoire/19_…` et `27_…`, même doi 10.48550/arXiv.2406.11665) : *See It from My Perspective*, ICLR 2025, porte sur des **modèles vision-langage en compréhension d'images**. Transposer sa conclusion à une tâche de décision textuelle n'est pas soutenable dans un texte relu en double insu. Ce qu'elle apportait est conservé sans citation, par la phrase du § 4.1 qui déclare qu'aucune mesure de ce travail n'établit que l'exécution en français dégradait les scores. Aucune entrée bib créée.

---

---

## A bis. Références de mémoire — déposées le 21 septembre 2026 (ticket 071)

Avant ce dépôt, l'article ne citait **aucune** référence de mémoire hors Reflexion, alors que
la section 3.4 décrit l'architecture de Park et al. adaptée par Vu et al. Les onze PDF sont
dans `etat_de_lart/` (§ 9 de son README) et leurs onze clés dans `sample.bib`.

⚠ **Les conditions 1, 2 et 4 sont remplies ; la 3 ne l'est pas.** Neuf de ces onze ne sont
citées nulle part dans le texte : leur phrase citante reste à écrire, et leur case reste donc
ouverte. Seules A49 et A50 sont déjà appelées par le texte.

⚠ **Restent hors dépôt et donc non citables :** les huit références de psychologie sous licence
éditeur et les trois ouvrages sans PDF. **Tulving (1972) est le cas à trancher** : le § 3.4 FR
et EN lui attribue la distinction épisodique / sémantique, sans PDF ni clé. Consulter l'ouvrage
et poser la mention, ou renoncer à l'attribution. Manifeste complet :
[`../../sources/DEPOT_MEMOIRE_TICKET_071.md`](../../sources/DEPOT_MEMOIRE_TICKET_071.md).

### A40. Sumers, Yao, Narasimhan & Griffiths (2024)
- [x] PDF : `etat_de_lart/Sumers_2024_CoALA.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 3.4 — à écrire ; la section décrit la distinction épisodique / sémantique portée aux agents de langue sans encore l'attribuer.
- À pointer : § 3, la taxonomie des mémoires d'un agent de langue.
- **Attribution :** paru dans *TMLR*, février 2024 — **pas** à NeurIPS 2023, notice recoupée le 14 septembre 2026. arXiv:2309.02427.
- Bib : `sumers2024coala` (créée le 21 septembre 2026).

### A41. Zhong, Guo, Gao, Ye & Wang (2024)
- [x] PDF : `etat_de_lart/Zhong_2024_MemoryBank.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 3.4 — à écrire ; la courbe d'oubli et le renforcement au rappel viennent de là.
- À pointer : § 3, la mise en œuvre de la courbe d'Ebbinghaus et le renforcement à chaque rappel.
- **Attribution :** actes **AAAI-24**. arXiv:2305.10250.
- Bib : `zhong2024memorybank` (créée le 21 septembre 2026).

### A42. Chhikara, Khant, Aryan, Singh & Yadav (2025)
- [x] PDF : `etat_de_lart/Chhikara_2025_Mem0.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : ch. 8 — à écrire ; les opérations sur les concepts sont désignées par le modèle, non par un seuil.
- À pointer : § 3, les opérations de mémoire décidées par le modèle.
- **Attribution :** préprint arXiv:2504.19413.
- Bib : `chhikara2025mem0` (créée le 21 septembre 2026).

### A43. Xu, Liang, Mei, Gao, Tan & Zhang (2025)
- [x] PDF : `etat_de_lart/Xu_2025_A-MEM.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : ch. 8 — à écrire. ⚠ À citer **avec sa divergence** : la voie par seuil de similarité y est décrite, et ce dépôt l'a écartée.
- À pointer : § 3, l'évolution des notes et le lien par similarité.
- **Attribution :** **NeurIPS 2025**. arXiv:2502.12110.
- Bib : `xu2025amem` (créée le 21 septembre 2026).

### A44. Packer, Wooders, Lin, Fang, Patil, Stoica & Gonzalez (2023)
- [x] PDF : `etat_de_lart/Packer_2023_MemGPT.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : ch. 8 — à écrire ; le *working context* est l'origine directe de la mémoire noyau du lot 4.
- À pointer : § 3.1, le *main context* et sa partition.
- **Attribution :** préprint arXiv:2310.08560.
- Bib : `packer2023memgpt` (créée le 21 septembre 2026).

### A45. Liu, Li & Ma (2025)
- [x] PDF : `etat_de_lart/Liu_2025_GATSim.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 3.4 — à écrire ; réflexion périodique et formation d'habitudes **en contexte transport**, le voisin le plus proche du dispositif.
- À pointer : § sur la mémoire de l'agent et la réflexion périodique.
- **Attribution :** préprint arXiv:2506.23306, v3 du 6 février 2026 — la version déposée. ⚠ Une citation de chiffre doit nommer la version.
- Bib : `liu2025gatsim` (créée le 21 septembre 2026).

### A46. Jiménez Gutiérrez, Shu, Gu, Yasunaga & Su (2024)
- [x] PDF : `etat_de_lart/Gutierrez_2024_HippoRAG.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : ch. 8 — à écrire, **comme piste seulement** : aucun mécanisme du dépôt n'en dérive, et le laisser croire serait faux.
- À pointer : § 2, l'indexation inspirée de l'hippocampe.
- **Attribution :** **NeurIPS 2024**. arXiv:2405.14831.
- Bib : `gutierrez2024hipporag` (créée le 21 septembre 2026).

### A47. Reimers & Gurevych (2019)
- [x] PDF : `etat_de_lart/Reimers_2019_Sentence-BERT.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 3.4 — à écrire ; le cadre dont `all-MiniLM-L6-v2` est un modèle.
- À pointer : § 3, l'architecture siamoise et l'usage des plongements de phrase.
- **Attribution :** **EMNLP-IJCNLP 2019**, p. 3982-3992. arXiv:1908.10084.
- Bib : `reimers2019sbert` (créée le 21 septembre 2026).

### A48. Papineni, Roukos, Ward & Zhu (2002)
- [x] PDF : `etat_de_lart/Papineni_2002_BLEU.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 3.4 — à écrire, et **uniquement pour ne pas appeler BLEU ce qui n'en est pas un**.
- À pointer : § 2, la définition de la précision n-gramme modifiée.
- **Attribution :** actes **ACL 2002**, p. 311-318. ACL Anthology P02-1040.
- Bib : `papineni2002bleu` (créée le 21 septembre 2026).

### A49. Shinn, Cassano, Berman, Gopinath, Narasimhan & Yao (2023)
- [x] PDF : `etat_de_lart/Shinn_2023_Reflexion.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 5, l'auto-réflexion verbale — **la phrase citante existe déjà**, c'est le dépôt qui manquait.
- À pointer : § 2, la boucle de réflexion verbale et sa mémoire épisodique.
- **Attribution :** **NeurIPS 2023**. arXiv:2303.11366v4. ⚠ Elle était citée dans le chapitre 5 **sans PDF ni clé** avant le 21 septembre 2026 : seule référence de mémoire que l'article nommait, et la seule à ne passer aucune des quatre conditions.
- Bib : `shinn2023reflexion` (créée le 21 septembre 2026).

### A50. Laplace (1814)
- [x] PDF : `etat_de_lart/Laplace_1814_Essai_Probabilites.pdf` (déposé le 21 septembre 2026, titre vérifié sur la première page).
- Phrase citante : § 3.4 et ch. 7, la règle de succession dont dérive la confiance d'un concept — **la phrase citante existe déjà au ch. 7**.
- À pointer : la règle de succession, dans la partie sur la probabilité des événements futurs.
- **Attribution :** ⚠ Le fichier déposé est la **réimpression Gauthier-Villars** (coll. « Les Maîtres de la Pensée Scientifique », éd. Solovine), **pas l'original Courcier de 1814** que la notice bibliographique donne. Numérisation d'archive du domaine public, sans couche de texte : la pagination à pointer est celle de la réimpression.
- Bib : `laplace1814essai` (créée le 21 septembre 2026).

---

## B. Entrées BibTeX créées (récapitulatif)

Créées le 8 septembre 2026 ; les listes d'auteurs de A21, A22 et A23 sont à confirmer sur le PDF (note dans le bib).

- [x] `adam2025survey` — A4 — créée dans sample.bib le 8 septembre 2026
- [x] `chopra2024limits` — A6 — créée dans sample.bib le 8 septembre 2026
- [x] `liu2024toward` — A7 — créée dans sample.bib le 8 septembre 2026
- [x] `bougie2025citysim` — A8 — créée dans sample.bib le 8 septembre 2026
- [x] `alves2026evaluating` — A9 — créée dans sample.bib le 8 septembre 2026
- [x] `vu2025modeling` — A10 — créée dans sample.bib le 8 septembre 2026
- [x] `argyle2023outofone` — A11 — créée dans sample.bib le 8 septembre 2026
- [x] `meister2024benchmarking` — A12 — créée dans sample.bib le 8 septembre 2026
- [x] `kambhatla2025improving` — A13 — créée dans sample.bib le 8 septembre 2026
- [x] `huang2025distribution` — A14 — créée dans sample.bib le 8 septembre 2026
- [x] `nguyen2025prompt` — A15 — créée dans sample.bib le 8 septembre 2026
- [x] `feng2024agentmove` — A19 — créée dans sample.bib le 8 septembre 2026
- [x] `secheresse2025gaapo` — A20 — créée dans sample.bib le 8 septembre 2026
- [x] `guo2023evoprompt` — A21 — créée dans sample.bib le 8 septembre 2026
- [x] `pryzant2023automatic` — A22 — créée dans sample.bib le 8 septembre 2026
- [x] `opsahlong2024optimizing` — A23 — créée dans sample.bib le 8 septembre 2026
- [x] `smith1995transims` — A28 — créée le 8 septembre 2026 (v0.3)
- [x] `grignard2018impact` — A29 — créée le 8 septembre 2026 (v0.3)
- [x] `oberoi2024personalisation` — A30 — créée le 8 septembre 2026 (v0.3)
- [x] `fourez2025transport` — A31 — créée le 8 septembre 2026 (v0.3)
- [x] `lammer2026gta` — A33 — créée dans sample.bib le 10 septembre 2026 (v0.14)

---

Ajoutées le 21 septembre 2026 (ticket 071), toutes dans `sample.bib` :
- [x] `sumers2024coala` — A40 — créée dans sample.bib le 21 septembre 2026
- [x] `zhong2024memorybank` — A41 — créée dans sample.bib le 21 septembre 2026
- [x] `chhikara2025mem0` — A42 — créée dans sample.bib le 21 septembre 2026
- [x] `xu2025amem` — A43 — créée dans sample.bib le 21 septembre 2026
- [x] `packer2023memgpt` — A44 — créée dans sample.bib le 21 septembre 2026
- [x] `liu2025gatsim` — A45 — créée dans sample.bib le 21 septembre 2026
- [x] `gutierrez2024hipporag` — A46 — créée dans sample.bib le 21 septembre 2026
- [x] `reimers2019sbert` — A47 — créée dans sample.bib le 21 septembre 2026
- [x] `papineni2002bleu` — A48 — créée dans sample.bib le 21 septembre 2026
- [x] `shinn2023reflexion` — A49 — créée dans sample.bib le 21 septembre 2026
- [x] `laplace1814essai` — A50 — créée dans sample.bib le 21 septembre 2026

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
- [ ] Jeu de test scellé des références tabulaires : 13 045 trajets, découpage par ménage — `scripts/progedo_logit/mode_choice_policy_metrics.json` (`test.n_rows`).
- [ ] Contrat de 21 variables, `spec_version 2` — `scripts/progedo_logit/feature_spec.json`.
- [ ] Jusqu'à six itinéraires présentés — `max_candidats: 6` dans `experience.yaml` des expériences jouées.
- [x] Corpus de 30 articles, 7 classés « éliminer » — plus mentionné dans l'introduction depuis la v0.7 (cinq articles, choisis avant tout appel) ; reste vrai pour l'annexe.
- [ ] Enquête EMC² 2023 : environ 16 000 répondants, 453 communes — rapport AUAT/CEREMA.
- [ ] Citation des microdonnées conforme au modèle de la convention `lil-1750` — libellé à recopier (A34) ; provisoire en Annexe G.
- [ ] Tout autre chiffre porte un tag **[xx.y | exp_id]** jusqu'à mesure sur le substrat scellé.

---

---

## E. Clés BibTeX

Le schéma de clés de l'exemple AAMAS (initiales + année, `WoJe95`) a été essayé le 8 septembre 2026 puis abandonné le même jour à la demande de l'auteur : les clés descriptives `auteurAnnéeMot` (`smith1995transims`, `horni2016matsim`) sont conservées. Le format des entrées reste celui de l'exemple AAMAS : valeurs entre accolades, seuls les champs renseignés sont écrits, acronymes des titres protégés.
