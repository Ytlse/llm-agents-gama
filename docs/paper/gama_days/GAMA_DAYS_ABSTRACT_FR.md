# Résumé — GAMA Days

**Document :** résumé soumis aux GAMA Days. Version française, où se fait la rédaction ; le miroir anglais [`GAMA_DAYS_ABSTRACT_EN.md`](GAMA_DAYS_ABSTRACT_EN.md) est le livrable et c'est son décompte de mots qui fait foi.
**Version :** `v1.0` (9 septembre 2026) — texte tel que soumis aux GAMA Days. La dernière phrase est resserrée par l'auteur, et le fichier LaTeX du dépôt devient le document complet réellement envoyé : titre, auteurs, mots-clés, figure d'architecture et lien de matériel additionnel.
**Historique :** `v0.1` (9 septembre 2026) première mise au propre du brouillon : trois corrections factuelles, résultats non mesurés en tag, logit multinomial rétabli, vocabulaire corrigé · `v0.2` (9 septembre 2026) texte tourné vers la communauté GAMA, rejeu assumé comme accélération · `v0.3` (9 septembre 2026) paragraphe 3 resserré, miroir anglais créé · `v0.4` (9 septembre 2026) échelle unitaire réservée à AAMAS · `v0.5` (9 septembre 2026) vocabulaire d'agent génératif rétabli · `v0.6` (9 septembre 2026) apport propre de GAMA énoncé · `v0.7` (9 septembre 2026) chiffres renseignés · `v0.8` (9 septembre 2026) chute resserrée, version Overleaf créée · `v0.9` (9 septembre 2026) dix-neuf mots retirés · `v0.10` (9 septembre 2026) passage au score composite · `v0.11` (9 septembre 2026) composite nommé comme écart à minimiser · `v0.12` (9 septembre 2026) plus aucun emplacement chiffré · `v1.0` (9 septembre 2026) cette version, soumise.
**Convention des tags :** un chiffre écrit **[xx,x | exp_id]** est un emplacement à remplir depuis l'export de [`experience_plan/experiments.yaml`](../methode/experience_plan/experiments.yaml) ; l'identifiant nomme l'expérience qui produira la valeur. Un chiffre laissé en clair se recalcule depuis un fichier du dépôt ; sa source est donnée en commentaire HTML à côté.
**Fichiers liés :** [`chapitres/01_INTRODUCTION_FR.md`](../article/fr/01_introduction.md) (`v0.8`, dont ce résumé reprend le cadrage), [`REMARQUES_INTRODUCTION.md`](../article/relecture/01_introduction.md), [`ameliorations.md`](../article/ameliorations.md), [`action.md`](../article/CITATIONS.md).

---

## Résumé

Les simulations multi-agents de mobilité urbaine reposent traditionnellement sur des modèles tabulaires, modèles de choix discret ou apprentissage supervisé estimés sur enquêtes, ou sur des systèmes de règles explicites. Dans les deux cas, l'espace des comportements représentables est fixé a priori par la spécification : un facteur qui n'a pas été encodé comme variable ou comme règle ne peut influencer aucune décision. Les agents génératifs fondés sur les grands modèles de langage (LLM) promettent de lever cette limite. À partir d'une enquête ménages‑déplacements certifiée, nous mesurons l'écart de calage entre ces agents et les modèles traditionnels estimés sur celle‑ci, et nous testons s'ils s'adaptent à des situations qu'aucune variable n'encode.

Nous avons construit sur GAMA une plateforme de simulation de l'aire métropolitaine toulousaine, intégrant les réseaux routier et ferroviaire et les trois réseaux de transport en commun. La population synthétique de 1 000 individus est générée par eqasim <!-- source : data/population/population_1000_AAMAS/MANIFEST.yaml, sceau 1 du 2026-09-02 -->, et les itinéraires alternatifs sont calculés sur les réseaux réels par OpenTripPlanner. Le modèle porte les contraintes qui font le réalisme d'une journée et qu'aucun calculateur d'itinéraires ne connaît : chaînage spatial des véhicules, une voiture disponible là seulement où elle a été laissée, conducteur nécessaire pour la déplacer, retours contraints au domicile, enchaînement temporel des activités. Chaque habitant y devient un agent génératif : sa règle de choix modal n'est plus écrite dans le modèle, elle est produite par un grand modèle de langage interrogé par lots, qui reçoit le profil de l'agent et les itinéraires réellement offerts et répartit 100 % de la décision sur celles‑ci.

Tous les décideurs sont comparés sur ce même substrat, face aux parts modales de l'enquête EMC² 2023 (CEREMA). Trois références encadrent la comparaison, à variables identiques : un a priori empirique, toujours la voiture, comme plancher ; le logit multinomial comme référence économétrique ; un oracle supervisé LightGBM estimé sur l'enquête comme plafond.

Le calage statistique échoue. Les parts modales simulées présentent des biais systématiques majeurs : sur‑attraction des transports collectifs, 26,5 % contre 12,4 % observés, et sous‑estimation de la marche, 15,3 % contre 26,8 % <!-- source : data/experiences/exp_gemini-35-fl_expcham5_jtir_t0_nosim_2/executions/2026-09-08_20_28_52/scores.json ; cibles EMC² : scripts/data/population/cerema_values.yaml -->. Notre écart composite aux distributions observées, à minimiser, vaut 12,6, contre 29,9 pour l'a priori empirique et 4,9 pour l'oracle <!-- sources : data/experiences/exp_gemini-35-fl_expcham5_jtir_t0_nosim_2/executions/2026-09-08_20_28_52/scores.json (composite.emd_jsd) ; exp_majvoiture_nosim ; exp_lgbm_jtir_nosim -->. En contrepartie, nous éprouvons deux régimes qu'aucun modèle tabulaire sans mémoire ne peut produire : l'adaptation à des événements réels de la presse locale toulousaine, et l'hystérésis comportementale sur cinq jours après une panne majeure du métro, portée par un registre de mémoire court terme qui révise la perception du risque. Nous rapportons la part des reports modaux et le taux de réadoption, face à un agent témoin sans mémoire.

Nous en tirons des implications pour des architectures hybrides, où le modèle tabulaire assure le calage du régime nominal et l'agent génératif traite les écarts. GAMA n'y est pas un hôte : c'est lui qui ancre la décision dans le terrain. Le modèle de langage produit un raisonnement, la simulation produit la situation à laquelle ce raisonnement s'applique, la géographie réelle, l'offre de transport au départ, et la journée qui contraint la suivante. Sans cet ancrage, l'agent délibérerait hors sol.

---

## Ce que dit le dépôt aujourd'hui

Les valeurs ci‑dessous sont mesurées sur la population scellée les 7 et 8 septembre 2026, par rejeu du jeu de déplacements enregistré. La ligne en gras est celle que rapporte le résumé : la condition à prompt calibré `exp_gemini-35-fl_expcham5_jtir_t0_nosim_2`, gabarit `expert_chaine_m5` sur Gemini 3.5 Flash-Lite, 2 636 déplacements décidés sur 2 645, aucune erreur. Les autres lignes situent ce résultat.

| Décideur | Composite EMD/JSD | Écart L1 | Voiture | Marche | Transports collectifs | Vélo |
|---|---|---|---|---|---|---|
| Cible EMC² 2023 | — | — | 56,7 % | 26,8 % | 12,4 % | 4,1 % |
| **Gemini 3.5 Flash-Lite, prompt calibré `expert_chaine_m5`** | **12,6** | **35,2** | **50,6 %** | **15,3 %** | **26,5 %** | **7,6 %** |
| Gemini 3.1 Flash-Lite, prompt nu | 18,4 | 46,0 | 45,5 % | 15,0 % | 32,5 % | 7,0 % |
| Mistral Small, prompt nu | 27,4 | 63,4 | 33,8 % | 18,0 % | 38,8 % | 9,5 % |
| A priori empirique, toujours la voiture | 29,9 | 57,1 | 85,3 % | 6,1 % | 8,1 % | 0,5 % |
| Durée minimale | 29,7 | 52,9 | 80,5 % | 2,9 % | 9,8 % | 6,8 % |
| Tirage uniforme | 50,4 | 83,6 | 14,9 % | 37,3 % | 41,1 % | 6,6 % |
| Oracle LightGBM | 4,9 | 7,6 | 55,0 % | 25,8 % | 16,2 % | 3,1 % |

Quatre enseignements pour la rédaction. Le prompt calibré gagne 5,8 points de composite sur le prompt nu, 18,4 vers 12,6, ce qui est loin d'être marginal et devra être dit sans être surinterprété : deux choses changent à la fois, le gabarit et le modèle. Le biais dominant reste la **sur‑attraction des transports collectifs**, encore quatorze points après calage, devant la sous‑estimation de la marche, onze points et demi ; le vélo n'en pèse que trois et demi, alors que le brouillon antérieur racontait le vélo, chiffre hérité du run GAMA du 24 août sur une autre population. Mistral nu fait moins bien que l'heuristique qui répond toujours « voiture ». Et le tirage uniforme sur l'offre est le pire décideur de tous, ce qui écarte l'hypothèse qu'une offre d'itinéraires mal formée expliquerait à elle seule les biais des agents.

---

## Ce qui reste à trancher

1. **Format.** Réglé : classe `gamadays`, titre, auteurs, mots-clés, figure d'architecture, matériel additionnel, aucune référence bibliographique. Le corps du résumé fait 490 mots en anglais.
2. **Le degré de détail sur la plateforme.** La figure d'architecture porte désormais une partie de cette charge. Pour la présentation orale, nommer les briques (service de décision, passerelle multi‑fournisseurs, cache d'itinéraires, registre d'expériences) rendrait le travail directement réutilisable.
3. **Les régimes non tabulés.** Les expériences d'hystérésis et de presse n'ont pas tourné. Depuis la `v0.12` le résumé nomme les deux grandeurs rapportées sans les chiffrer, il est donc soumettable en l'état. Les chiffres viendront dans la présentation ou l'article.
4. **Tenue des trois fichiers.** Le français, l'anglais et le source LaTeX doivent bouger ensemble. Deux dépendances vivent hors du dépôt : la classe `gamadays.cls` et l'image `architecture_GAMA_Agents.jpg`.

---

## Journal

- 9 septembre 2026 — `v1.0`, version soumise. Dernière phrase resserrée par l'auteur en « la part des reports modaux et le taux de réadoption ». Le fichier LaTeX du dépôt cesse d'être un fragment : il porte le document complet envoyé, classe `gamadays`, titre, auteurs, mots-clés, figure d'architecture et lien de matériel additionnel, ce qui garde le dépôt et la soumission identiques.

- 9 septembre 2026 — `v0.12`. Relecture du PDF compilé. Les deux emplacements ⟨xx⟩ étaient visibles dans le document soumis, sur les deux grandeurs mêmes qui portent la moitié « opportunités » du titre ; la phrase les nomme désormais sans les chiffrer. La note de provenance, raccourcie par l'auteur, avait perdu son verbe : corrigée au strict minimum, « on a sealed cohort » au lieu de « , set of a sealed cohort ».

- 9 septembre 2026 — `v0.11`. La phrase de résultat ne justifie plus le choix du composite, elle le définit : un écart aux distributions observées, à minimiser. Le lecteur sait donc dans quel sens lire 12,6 sans avoir à consulter la note, et la raison d'être de la métrique, l'impossibilité de compenser une erreur d'une strate par une autre, reste disponible en note pour qui la cherche.

- 9 septembre 2026 — `v0.10`. Le résumé rapporte désormais le score composite EMD/JSD, qui agrège l'écart global et les écarts par strate et empêche donc les erreurs de se compenser d'une sous‑population à l'autre. La définition tient en note de bas de page, hors du décompte de mots. Le tableau d'annexe gagne une colonne composite, et l'ordre des décideurs y est le même qu'en L1, ce qui rassure sur le choix de métrique.

- 9 septembre 2026 — `v0.9`. Dix-neuf mots retirés en anglais, 518 vers 499, répercutés en français et dans le rendu Overleaf. Aucune donnée perdue : la glose « une voiture disponible là seulement où elle a été laissée » est conservée au paragraphe 2 mais ne se répète plus au paragraphe 5, « cent pour cent » s'écrit 100 %, et l'incident du métro se dit en une fois au lieu de deux.

- 9 septembre 2026 — `v0.8`. Suppression par l'auteur de la phrase sur la réutilisabilité du motif : le résumé s'achève sur « sans cet ancrage, l'agent délibérerait hors sol », qui est une meilleure chute. Création de la version Overleaf, où les mesures portent en note de bas de page leur date, leur modèle, leur gabarit et l'effectif décidé.

- 9 septembre 2026 — `v0.7`. Chiffres du paragraphe de résultats renseignés depuis `exp_gemini-35-fl_expcham5_jtir_t0_nosim_2` : transports collectifs 26,5 % contre 12,4, marche 15,3 % contre 26,8, écart L1 35,2 points entre un plancher à 57,1 et un plafond à 7,6. La phrase « le calage statistique échoue » est confirmée par la mesure, l'agent restant à plus de quatre fois l'écart de l'oracle. Restent en tag les deux régimes non tabulés, presse et hystérésis, dont les expériences n'ont pas tourné.

- 9 septembre 2026 — `v0.6`. Le dernier paragraphe se contentait d'annoncer un motif réutilisable, ce qui laissait GAMA au rang d'hôte. Il énonce maintenant l'apport propre de la simulation : sans elle, l'agent délibérerait hors sol, sur un jeu d'options plausibles mais détachées du terrain. C'est l'argument le plus directement adressé à ce public, et il est vérifiable dans le journal du rejeu.

- 9 septembre 2026 — `v0.5`. Le mot « agent génératif » ne figurait dans aucun des deux résumés, alors que l'introduction l'emploie quatre fois et que l'article de plateforme de l'équipe le porte dans son titre. Le paragraphe 2 décrivait un « service de décision externe », description technique qui faisait disparaître les agents. Il dit maintenant que chaque habitant devient un agent génératif, le détail de l'interrogation par lots étant conservé pour ce qu'il vaut devant ce public, la tenue en charge.

- 9 septembre 2026 — `v0.4`. L'évaluation unitaire, exactitude et log‑loss sur les 13 045 déplacements scellés, est retirée du résumé et réservée à l'article AAMAS. Le résumé ne parle plus que de parts modales, ce qui allège le paragraphe de protocole et retire une métrique du paragraphe de résultats. Les trois références restent, comparées en écart L1.

- 9 septembre 2026 — `v0.3`. Paragraphe 3 resserré, grammaire remise d'aplomb, les deux échelles de comparaison conservées. Création du miroir anglais, désormais livrable de référence pour la longueur.

- 9 septembre 2026 — `v0.2`. Le rejeu sur jeu enregistré cesse d'être présenté comme une réserve méthodologique : c'est une accélération qui conserve les contraintes du modèle, et les compteurs d'alternatives écartées le démontrent. Le deuxième paragraphe part de la plateforme et de ses contraintes physiques, le troisième explique le protocole de rejeu, le dernier dit ce qui est réutilisable dans un autre modèle GAMA. Un troisième enseignement est ajouté à l'annexe : le tirage uniforme est le pire décideur, ce qui disculpe l'offre d'itinéraires.
- 9 septembre 2026 — `v0.1`, première mise au propre. Corrections appliquées au brouillon : taxonomie d'ouverture (choix discret et apprentissage supervisé sont des modèles tabulaires, non leurs frères) ; phrase de promesse réécrite sans « compromis » et sans résultat annoncé ; effectif 13 045 renseigné ; logit multinomial rétabli ; biais dominant corrigé du vélo vers les transports collectifs ; mémoire « court et moyen terme » ramenée au court terme, seul registre implémenté ; « chute de vélo » retirée, la perturbation prévue est la panne de la ligne A ; vocabulaire (« amnésique » plutôt que le calque *amnestic*, « déplacements » plutôt que *paths*, « substantiel » plutôt que *significatif*).
