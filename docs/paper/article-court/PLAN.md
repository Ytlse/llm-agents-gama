# Plan de l'article court — AAMAS 2027

Écrit le 2026-09-22. **Hypothèse de travail : le ticket 103 est réglé dans son scénario 1**
(Jev tient hors échantillon, le carré est carré, les écarts publiés survivent aux graines).
Le § 8 dit ce qui change dans les scénarios 2 et 3. Les chiffres cités viennent de l'état des
masters `docs/paper/article/fr/` au 2026-09-22 ; ceux qui doivent être remesurés sur la
seconde cohorte sont marqués `[c2]`.

> **⚠ 2026-09-24 — décision de l'auteur, qui prime sur tout `[c2]` de ce plan.** La cohorte
> scellée (`population_1000_AAMAS_v6`, jeu `…_20260316_EN_c`) sert à la mesure seule ; la
> seconde (`population_1000_AAMAS_v6_c2`) est la **cohorte de calibration**, sur laquelle les
> prompts se règlent. Termes d'article : « sealed cohort » et « calibration cohort ». Les
> emplacements `[c2 : …]` des §§ 4.4 et 5.3 se lisent donc « score sur la cohorte scellée
> d'un prompt réglé sur la cohorte de calibration ». Le carré « tous hors échantillon sur une
> seconde cohorte » (§ 5.3) se mesure sur la cohorte scellée.

---

## 0. Fiche

| | |
|---|---|
| **Titre proposé** | *Where Chain-of-Thought Earns Its Place: Generative Mobility Agents Against a Real Household Travel Survey* (retenu le 2026-09-23 ; en français : *Là où le chain-of-thought mérite sa place : des agents génératifs de mobilité face à une enquête ménages déplacements réelle*) |
| **Thèse** | Dans une population d'agents de mobilité, la délibération verbalisée n'améliore pas la fidélité au régime que l'enquête décrit ; ce qu'elle apporte, c'est la prise en compte d'événements qu'aucune variable n'encode, dont nous traçons le chemin jusqu'à la décision. |
| **Relecteur visé** | Celui qui évalue des populations d'agents LLM contre des ancrages humains : la conversation de SILICA, Baronchelli, Argyle, Meister. Pas le relecteur transport, pas le relecteur systèmes. |
| **Format** | 8 pages, figures et tableaux compris ; références hors limite ; annexes en matériel supplémentaire. |
| **Budget de prose** | 5 200 mots, 5 figures, 3 tableaux. |
| **Langue** | Français source, anglais rédigé depuis le sens (consigne R17). |
| **Contrôle** | `verifier_forme.py` sur chaque section avant relecture ; `make paper-style` ensuite. |

### Ce que le papier établit, en quatre phrases

1. Sur une cohorte synthétique contrôlée de Toulouse, un agent génératif calibré atteint les
   modèles tabulaires estimés sur l'enquête sans les dépasser.
2. Un classifieur à sortie typée, qui lit le même contexte et n'écrit rien, atteint la même
   bande `[c2]`, pour un cinquantième du coût.
3. Deux décideurs indissociables sur les marges agrégées peuvent différer d'une décision sur
   trois individu par individu, et l'un d'eux tomber sous une règle constante.
4. Ce que la délibération fait, et que rien d'autre n'a fait dans nos mesures, c'est recevoir un
   événement non tabulé, l'écrire en mémoire et le laisser s'éteindre ; nous montrons par quel
   canal, sur un cas tracé de bout en bout.

### Les trois contributions

| | Contribution | Ce qui la porte |
|---|---|---|
| **C1** | Un banc de comparaison à entrées égales entre agents génératifs et modèles tabulaires, sur une cohorte synthétique contrôlée contre une enquête certifiée | § 3, § 4 |
| **C2** | Le positionnement de quinze décideurs sur ce banc, et deux dissociations que les marges agrégées ne voient pas | § 5 |
| **C3** | Le chemin tracé d'un événement non tabulé jusqu'à la décision, dans un agent génératif à mémoire | § 6 |

**Ce qui n'est pas une contribution :** l'architecture en cascade. Elle n'est ni construite ni
mesurée. Elle vit au § 7 comme implication, avec sa contradiction dite (§ 7.1.3).

---

## 1. Introduction — 700 mots

**Ce qu'elle établit :** pourquoi la question se pose, pourquoi personne n'y a répondu, ce que
ce papier répond.

### 1.1 La promesse des agents génératifs — 180 mots
- Les simulations existantes : modèles tabulaires estimés sur enquêtes, ou règles d'experts.
  Dans les deux cas l'espace des comportements est fixé a priori.
- La promesse : des heuristiques que l'enquête n'enregistre pas, une adaptation sans règle
  explicite. Une grève, une canicule, une rumeur dans le métro.
- Reprendre les phrases du tuteur validées dans l'abstract v1.9 : elles sont bonnes.

### 1.2 Personne ne sait évaluer cette promesse contre une population réelle — 200 mots
- Les évaluations publiées comparent à des agents à règles, ou à des motifs de leur propre
  fabrication.
- GTA (Lammer 2026) est le seul à confronter une répartition modale simulée à une enquête
  nationale, et il se donne pour référence la répartition d'autres régions : copier Hambourg
  fait mieux que sa simulation (1,99 contre 4,07). Une phrase, pas un paragraphe.
- Ce qui manque : un plancher sous les agents, des modèles calibrés au-dessus, les mêmes
  entrées pour tous. Et une mesure qui descende sous l'agrégat.

### 1.3 Ce que ce papier fait — 220 mots
- La thèse, en une phrase, celle de la fiche.
- Les trois contributions, C1 à C3, une ligne chacune.
- Le terrain : Toulouse, EMC² 2023, 1 000 personas, 3 299 déplacements, quinze décideurs.
- **Ni H0, ni paliers 0-3, ni C1/C2/C3 au sens « conditions ».** Un seul système de noms
  (consigne R12).

### 1.4 Organisation — 100 mots
Six lignes, une par section, sans reprendre le contenu.

**Sort de l'introduction actuelle :** § 1.2 SILICA développé (une phrase au § 2 suffit), les
deux régimes du § 1.6 avec leurs placeholders, l'annonce de la presse, les treize marges,
les 13 045 trajets du jeu de test.

---

## 2. Travaux liés — 450 mots

**Ce qu'il établit :** trois littératures, une phrase chacune sur ce qu'elle laisse ouvert.

### 2.1 Le choix modal et son plafond comportemental — 130 mots
- Utilité aléatoire, logit, estimation sur enquête (McFadden, Ben-Akiva, Train). Force
  statistique, faiblesse comportementale.
- Adam et al. 2025 : les filtres de perception existent et l'enquête ne les enregistre pas.
  C'est la brèche par laquelle les agents génératifs sont proposés.

### 2.2 Agents génératifs en simulation de mobilité — 180 mots
- Park et al. 2023 pour l'architecture ; Liu et al. 2024 pour la vision hybride.
- GTA en une phrase de plus que l'introduction : un mode par déplacement, pas de métrique
  distributionnelle, pas de mémoire multi-jours. Ce que nous ajoutons.
- Alves et al. 2026 : GAMA + LLM + mémoire, sans vérité terrain humaine.
- **Sortent :** MATSim développé, CitySim développé, Chopra sur les archétypes (une demi-phrase
  au § 7 suffit).

### 2.3 Alignement distributionnel des populations de LLM — 140 mots
- Argyle 2023, Meister 2024 (verbaliser vaut mieux que tirer : c'est ce qui justifie la
  règle 2 du protocole), Kambhatla 2025, Huang 2025.
- Baronchelli 2025-2026 : les populations de LLM ne sont pas des proxys humains.
- SILICA : grille de lecture et contrôle de l'ordre des options. **Ne pas écrire « en accord
  avec SILICA »** au sujet de nos résultats : SILICA mesure des jeux, pas le choix modal, et le
  § 1.2 actuel le dit. Le § 9 actuel se contredit sur ce point ; l'article court ne le fait pas.
- **La délibération verbalisée aide-t-elle ?** Une phrase sur le débat chain-of-thought contre
  sortie directe, et pourquoi le cas des distributions de population n'y est pas tranché.
  C'est la littérature que le § 5.3 affronte ; si elle n'est pas nommée ici, un relecteur écrit
  « connu ».

---

## 3. L'agent évalué — 450 mots

**Ce qu'il établit :** ce que l'agent reçoit, ce qu'il rend, et les deux mécanismes que les
§ 5 et § 6 mettent à l'épreuve : la masse de probabilité et la mémoire.

### 3.1 La boucle — 120 mots
- GAMA porte le monde, un contrôleur porte le cycle de vie, un module de décision porte le
  choix. Un agent immobile déclenche une planification, reçoit les itinéraires, répartit sa
  préférence, la simulation exécute et renvoie ce qui s'est passé.
- **Figure 1**, l'architecture, en pleine largeur. Légende en une affirmation.
- **Sort :** le quadruplet formel, l'ordonnancement par échéance, le week-end.

### 3.2 Ce que l'agent reçoit et ce qu'il rend — 130 mots
- L'observation : profil court, destination, heure, météo, agenda restant, souvenirs
  pertinents, liste numérotée des itinéraires viables.
- Il **répartit une masse de probabilité** sur les options, une entrée par option. La décision
  jouée est un tirage dans ce vecteur, jamais un argmax. Ordre des options randomisé.
- C'est ce qui rend la comparaison distributionnelle du § 4 possible : une phrase, pas une
  démonstration.

### 3.3 Deux registres de mémoire — 130 mots
- Court terme : tampon circulaire, reçoit l'expérience physique produite par la simulation.
- Long terme : traces épisodiques qui s'érodent (constante 2,8 jours, allongée par la gravité),
  concepts qui ne s'érodent pas et vivent sur une confiance.
- Le modèle ne reçoit pas les souvenirs bruts : ce que l'agent fait le plus souvent, ce qu'il
  tient pour vrai, **ce qui a changé récemment**. Nommer ce bloc ici : le § 6 montre que c'est
  lui qui a porté l'effet.
- **Sort :** la figure des deux horloges (annexe), le score de rappel à cinq termes, le
  réajustement d'horaire à 75 %.

### 3.4 La chaîne de véhicules — 70 mots
- Un agent parti à vélo n'a pas sa voiture le soir. Trois règles. Elle s'applique à **tous** les
  décideurs comparés, tabulaires compris : sans elle on comparerait des décisions prises dans
  des mondes différents.

---

## 4. Le banc de comparaison — 900 mots

**Ce qu'il établit :** C1. C'est la section méthodologique la plus longue, et c'est voulu :
c'est le gros du travail et c'est ce qui rend chaque chiffre du § 5 attribuable.

### 4.1 La cohorte — 200 mots
- 1 000 personas en 499 ménages entiers, tirés d'un vivier eqasim de 11 329 personnes ;
  périmètre des 453 communes de l'enquête.
- Treize marges contrôlées contre l'enquête, toutes conformes à ±1 point, écart maximal
  0,50 (classe d'âge et occupation). **Une phrase, et le tableau en annexe A** : la table de
  treize lignes « conforme » ne porte pas d'information en corps de texte.
- Chaînes cycliques : 3 299 déplacements, 3,30 par persona et 3,69 par mobile ; l'enquête donne
  3,53 et 3,95. Dire l'écart.
- **Ce qui est diffusable et ce qui ne l'est pas** : la convention `lil-1750` interdit les
  microdonnées et le jeu de test scellé ; le protocole, le code et les marges agrégées sortent ;
  le statut de la cohorte dérivée est à trancher. Écrit ici, pas en limite.

### 4.2 Le protocole en trois règles — 250 mots
- **Règle 1, les mêmes 21 variables** : douze pour la personne et le ménage, trois pour le
  déplacement, six pour la géométrie. Liste en annexe B.
- **Règle 2, la masse de probabilité est la quantité scorée**, pas le mode le plus probable.
  Justification en une phrase : garder l'argmax aplatirait la variabilité individuelle que la
  population est chargée de reproduire (et Meister 2024).
- **Règle 3, renormalisation sur l'offre** : toute prédiction tabulaire est restreinte aux modes
  réellement proposés pour ce déplacement, puis renormalisée.
- **Les asymétries déclarées, en toutes lettres et au même endroit** : l'agent reçoit en plus
  l'agenda, la météo et les itinéraires détaillés ; les références tabulaires ont lu 39 203
  déplacements d'enquête que l'agent n'a jamais vus. Ce qui est égalisé, ce sont les variables,
  pas l'information. Ce paragraphe est ce qui désarme l'objection ; il ne se cache pas en § 8.

### 4.3 Ce qui est mesuré — 200 mots
- Deux échelles : agrégée (la répartition est-elle celle du territoire ?) et unitaire (ce
  déplacement-là a-t-il reçu le mode déclaré ?).
- Quatre modes, cinq strates, un composite EMD–JSD : **une seule équation**, celle du composite,
  avec L1, JSD et EMD nommés en une ligne chacun. Les trois autres en annexe C.
- Résolution : ±1,3 point de composite par bras, rééchantillonnage par grappe au niveau de la
  personne. Ce chiffre revient au § 5 ; le poser ici.
- Unitaire : exactitude, entropie croisée, rappel et précision par mode, sur les journées
  déclarées de l'enquête (2 930 personnes, 9 621 déplacements). Deux phrases.

### 4.4 Planchers, références, décideurs — 250 mots
- Trois planchers : hasard uniforme sur l'offre, tout-voiture, durée minimale.
- Quatre références tabulaires ajustées sur les microdonnées : logit multinomial, gradient
  boosté, régression logistique à noyau, forêt aléatoire. Parité stricte d'estimation. Aucune
  ne domine sur les deux lectures ; le plafond se lit lecture par lecture.
- Trois familles de décideurs sous test : **modèles de langue sous prompt minimal** (factuel,
  sans consigne d'arbitrage), **les mêmes sous prompt expert** (quatre principes d'arbitrage
  qualitatifs, sans seuil numérique ni label d'enquête, réglés sur une population de
  calibration séparée), et **un classifieur à sortie typée** qui lit le même texte et rend une
  probabilité par option sans écrire une ligne.
- Comment le prompt expert a été obtenu : cinq phrases sur les mutations réflexives et les
  trois garde-fous. Le texte intégral en annexe D. **Dire ici que le prompt du classifieur typé
  a été réglé séparément, et que le § 5.3 le mesure hors échantillon `[c2]`.**
- **Tableau 1** : les quinze décideurs, deux lectures, plus une colonne « étendue sur trois
  graines » pour les décideurs qui l'ont (ticket 103, lot B). Caption au-dessus.

---

## 5. Résultats au régime nominal — 1 400 mots

**Ce qu'il établit :** C2. Quatre sous-sections, quatre constats, chacun tenant en une phrase
de tête. Le § 5 s'ouvre par ces quatre phrases, puis les développe.

### 5.1 Quinze décideurs sur une échelle — 300 mots
- **Figure 2, la figure maîtresse** : l'axe du composite, cinq groupes qui se séparent. Facteur
  douze entre le plancher aléatoire et le meilleur composite.
- Les planchers de 27 à 50 ; le prompt minimal de 7,0 à 14,8, **déjà sous l'heuristique de
  durée minimale** : les faits seuls portent une information comportementale ; le prompt expert
  de 4,9 à 9,0 ; les tabulaires de 3,60 à 4,09.
- La dispersion inter-graines : étendue de 0,56 pour gemini-3.5 × expert (4,86 / 4,65 / 4,30),
  `[lot B]` pour les autres. Une phrase : sous la résolution de cohorte, et aucun signe d'écart
  publié ne change.
- **Le modèle pèse autant que l'instruction** : 4,2 points entre deux modèles du même fournisseur
  pour le même texte. Une phrase, en constat, pas en découverte (deux versions d'une famille).

### 5.2 Ce que la calibration déplace, et ce qu'elle ne déplace pas — 350 mots
- **Tableau 2** : gains appariés du prompt expert sur le prompt minimal, deux lectures,
  intervalles à 95 %. +2,27 [+1,40 ; +3,22], +3,37, +7,25 sur le composite ; tous excluent zéro ;
  de une fois et demie à cinq fois et demie la variation de cohorte.
- **Figure 3** : la part voiture par tranche de distance. Le prompt minimal est plat entre 40
  et 50 % là où l'enquête monte de 18 à 77 % ; le prompt expert retrouve la pente.
- Ce qui ne bouge pas : le vélo à 6,8-8,1 % contre 4,1 % observé, déplacé d'un dixième à huit
  dixièmes de point là où les transports en commun reculent de quatre à onze points. Le pic TC
  des 15-19 ans, 47,4 % dans l'enquête, qu'aucun décideur ne reproduit (20,8 % après réglage,
  26,4 % pour la forêt). Deux erreurs coexistent, une seule répond à l'instruction.
- Le prompt expert est **hors échantillon** pour gemini (population de calibration séparée) :
  une phrase, ici, pour que le § 5.3 puisse s'y référer.

### 5.3 La délibération n'est pas ce qui décide — 400 mots
- Phrase de tête : un classifieur à sortie typée, qui lit le même contexte et n'écrit rien,
  entre dans la bande des quatre références tabulaires `[c2 : composite A6, paires A6 × A7–A10]`.
- Le carré `[c2]` : deux modèles × trois prompts, tous hors échantillon sur une seconde cohorte
  sans persona commun. Ce que le prompt réglé pour le classifieur fait au modèle génératif, et
  réciproquement (Q2 du ticket 103). **La phrase de conclusion de ce paragraphe se choisit
  après lecture des scores, pas avant.**
- Ce que cela veut dire : la connaissance qui permet d'approcher la répartition d'un territoire
  est dans la lecture du contexte, pas dans la justification rédigée. Formuler comme un constat
  sur nos mesures, pas comme une loi : « dans nos mesures, la génération de texte n'a pas
  contribué à la fidélité agrégée ».
- Le coût : facteur cinquante, et pas pour la raison attendue. Le classifieur envoie plus de
  tokens d'entrée (1 050 contre 629), c'est le tarif qui change. Deux phrases ; le détail au
  § 7.
- **Ce paragraphe est le pivot du papier.** Il ne porte aucun chiffre en échantillon.

### 5.4 L'agrégat ne dit pas l'individu — 350 mots
- Phrase de tête : deux décideurs indissociables sur la répartition agrégée peuvent différer
  d'une décision sur trois individu par individu.
- **Tableau 3**, l'accord unitaire sur les journées déclarées : exactitude, entropie croisée,
  rappel vélo et marche, pour le gradient boosté, le logit, la durée minimale, les deux prompts
  gemini-3.5, et le classifieur typé.
- Le désaccord sur le mode le plus probable : 30,3 % entre l'agent et les tabulaires, 8,4 à
  11,0 % entre tabulaires. Les quatre méthodes forment un bloc ; l'agent n'en fait pas partie.
- **Le classifieur typé sous le plancher tout-voiture** : −2,42 point d'exactitude
  [−4,26 ; −0,62], alors qu'aucune paire ne le sépare des tabulaires sur l'agrégat. Une
  population peut restituer la répartition d'un territoire en se trompant, individu par
  individu, plus souvent qu'une règle qui ne regarde rien.
- **La fuite de cible** : une variante à 93,4 % d'exactitude sur l'enquête a produit le pire
  composite en simulation (9,28 contre 7,40), la distance reconstruite depuis la durée déclarée
  contenant le mode. Trois phrases. Leçon : noter le modèle là où il sert, pas là où il est
  facile de le noter. C'est ce qui justifie que le banc du § 4 ait été construit comme il l'a été.
- **Figure 4** : rappel et précision par mode, ou la matrice de désaccord ; choisir celle qui
  porte le −2,42 le plus lisiblement.

---

## 6. Le régime non tabulé : un événement tracé jusqu'à la décision — 750 mots

**Ce qu'il établit :** C3. Le titre porte « single-agent » en anglais. Ce que la section
revendique est le chemin causal, pas l'amplitude.

### 6.1 Ce que les 21 variables ne portent pas — 80 mots
- Aucune ne dit ce que la personne a vécu la veille, ni ce qu'elle a lu le matin. Un décideur
  qui ne reçoit que ces 21 entrées ne peut répondre à rien d'autre : son écart entre la veille
  et le lendemain d'un incident est nul par identité, pas par mesure.

### 6.2 Le mécanisme — 200 mots
- Entrée : après un déplacement pour le vécu, au réveil pour le lu. L'agent note gravité et
  valence ; cette note seule fixe la sévérité, et donc la durée de service du souvenir.
- Propagation : un saut, dans le foyer, le soir. Pas plus loin.
- Extinction : par contradiction (le déplacement refait sans que rien ne se reproduise) ou
  par usure (le souvenir cesse d'être servi). Les deux se distinguent à la mesure.
- **Ce qui est démontrablement de la génération** : écrire la trace et entretenir la croyance.
  Noter la gravité ne l'est pas nécessairement ; aucune expérience ici ne l'a testé sur le
  classifieur typé. Dire les deux, dans cet ordre (commentaire du § 1.3 actuel, ticket 101).

### 6.3 Le dispositif — 120 mots
- Un agent joué deux fois, exposé et témoin. Une panne de moteur qui impose un retard sur un
  trajet voiture, puis un retard moindre le lendemain. La voiture reste offerte : condition
  pour mesurer un arbitrage et non une contrainte, et dit comme n'étant pas ce qu'une vraie
  panne produirait.
- Six critères d'opinion déclarés, interrogés hors décision à quatre jalons ; le critère
  environnement, que rien ne vise, sert de question témoin.

### 6.4 Résultats — 350 mots
- **Figure 5** : la propension quotidienne à la voiture, exposé et témoin. De 90 % la veille à
  40 % le jour même, puis entre 5 et 52 % pendant une quinzaine, retour dans la bande du témoin
  (65-90 %) le 15 avril. **Un tableau de trois lignes** pour les fréquences (34/36 → 12/38 →
  35/40 contre 28/31, 45/49, 40/46), en pourcentages (consigne R13). L'offre de voiture ne
  change pas ; l'usage change.
- **Le chemin** : des quatre canaux par lesquels le passé atteint une décision, un seul a porté
  l'effet, le bloc « ce qui a changé récemment », présent dans 75 des 376 prompts, du jour de la
  panne au quinzième jour. Le rappel par similarité n'a jamais ramené le souvenir. La croyance
  consolidée n'a atteint aucun prompt. La durée de service découle de la sévérité, pas d'un
  nombre de jours fixé à la main.
- **L'extinction** : douze reprises de la voiture sans contradiction enregistrée, la croyance
  n'étant pas servie. C'est l'usure, pas la contradiction. Le récit disparaît des prompts le 13,
  la propension rejoint le témoin le 15 : deux dates lues sur deux sources indépendantes.
- **Les opinions** : cinq critères de la voiture sur six chutent au jalon suivant la panne et
  retrouvent leur valeur aux deux suivants ; l'environnement ne bouge pas ; le témoin ne bouge
  sur rien. Les quatre autres modes dérivent sans motif commun : c'est ce qui rend l'écart
  attribuable à la panne.
- La presse : **deux phrases**. Cinq articles réels et datés, vingt signes écrits avant tout
  appel, protocole en annexe E, campagne en cours. Pas un chiffre.

---

## 7. Implications, limites, conclusion — 550 mots

### 7.1 Ce que ces résultats disent d'une architecture — 250 mots
- Le coût d'une journée : 2 108 sollicitations, 3 millions de tokens mémoire désactivée, 2,5 de
  plus avec ; à l'échelle des 453 communes, 2,9 millions de sollicitations et 2,6 à 4,2 milliards
  de tokens par jour simulé. Ce chiffre commande de choisir où l'on délibère.
- La division du travail que nos mesures suggèrent : un étage déterministe retire l'impossible ;
  un modèle tabulaire ou un classifieur typé tient le régime nominal ; un modèle de langue
  reçoit, note et écrit en mémoire ce qu'aucune variable ne porte.
- **La contradiction, dite** : le décideur bon marché qui tient l'agrégat tombe sous une règle
  constante sur l'individu (§ 5.4). Une cascade qui le placerait en décideur achète la fidélité
  agrégée à bas coût et perd la fidélité individuelle. Un décideur qui lise le contexte, tienne
  l'agrégat et batte la constante sur l'individu n'existe pas dans nos mesures. C'est le
  problème que ce papier laisse ouvert, et il le dit.
- Pas de figure de cascade avec des parts de flux vides. Pas de `\todo`.

### 7.2 Limites — 150 mots
Quatre, une phrase chacune, sans plaidoyer : l'asymétrie d'exposition (39 203 déplacements lus
d'un côté, zéro de l'autre) ; l'hypothèse d'indépendance des alternatives non pertinentes que
la renormalisation suppose ; le cas unique du § 6 ; la non-diffusabilité des microdonnées.

### 7.3 Conclusion — 150 mots
Les quatre phrases de la fiche, dans l'ordre, puis ce qui reste ouvert : le décideur qui
manque, et la campagne de presse.

---

## 8. Ce qui change selon l'issue du ticket 103

| Issue | § 5.3 | § 7.1 | Titre |
|---|---|---|---|
| **Scénario 1** — Jev dans la bande hors échantillon | tel quel | tel quel | tel quel |
| **Scénario 2** — à moins de 1,3 point au-dessus | phrase de tête : « atteint le voisinage de la bande sans générer de texte » ; le facteur cinquante porte l'argument | tel quel | tel quel |
| **Scénario 3** — à plus de 1,3 point | devient un paragraphe du § 5.2 : « le résultat en échantillon ne s'est pas transporté » ; C2 perd un constat sur quatre | l'étage nominal revient au modèle tabulaire seul ; le classifieur typé sort de l'architecture | *Where Verbalised Deliberation Belongs* devient *What Verbalised Deliberation Adds*, la thèse restant celle des trois autres constats |
| **Q3 : un signe change sur une graine** | l'écart concerné ne se publie pas, quelle que soit sa taille | | |

---

## 9. Inventaire

### Figures (5)
| # | Contenu | Largeur | Source | Affirmation de légende |
|---|---|---|---|---|
| 1 | Architecture | pleine | `images/architecture_GAMA_Agents.jpg` | Le modèle de langue intervient en un point de la boucle, et c'est ce point que le papier met à l'épreuve. |
| 2 | Quinze décideurs sur l'axe du composite | pleine | `plot_chapitre6.py`, à régénérer avec la colonne graines | Cinq groupes se séparent ; le prompt minimal passe déjà sous l'heuristique physique. |
| 3 | Part voiture par distance | colonne | `ch6_distance.png` | Le prompt minimal ne voit pas la distance ; le prompt expert retrouve la pente. |
| 4 | Rappel et précision par mode, ou matrice de désaccord | colonne | `plot_audit_unitaire.py` | Deux décideurs indissociables sur l'agrégat diffèrent une fois sur trois sur l'individu. |
| 5 | Propension quotidienne à la voiture, exposé et témoin | colonne | `ch7_choc_figures.py`, axes en anglais | L'effet dure ce que dure le souvenir dans le prompt, et pas un jour de plus. |

### Tableaux (3)
| # | Contenu | Largeur | Caption |
|---|---|---|---|
| 1 | Quinze décideurs, deux lectures, étendue inter-graines | pleine | au-dessus |
| 2 | Gains appariés du prompt expert, deux lectures, IC 95 % | pleine | au-dessus |
| 3 | Accord unitaire, six décideurs | colonne | au-dessus |

### Annexes (matériel supplémentaire, hors des 8 pages)
- A — Les treize marges de la cohorte, sources et écarts.
- B — Les 21 variables du protocole.
- C — Les quatre métriques en équations, et la formule du composite avec ses poids.
- D — Le prompt minimal et le prompt expert, textes intégraux ; un cas d'inférence complet.
  **Rédigée** en anglais le 2026-09-24 dans `sections/08_appendices.en.md` : les trois prompts
  (le prompt du classifieur typé compris), quatre liens vers le dépôt anonyme, un trajet de la
  première cohorte sous les trois décideurs. Destination : PDF supplémentaire séparé, rendu
  dans `overleaf/chapters/08_Appendices.tex` et compilé par `overleaf/supplementary.tex`.
- E — Le protocole presse : cinq événements, trois conditions, grille des vingt signes.
- F — Résultats par strate et par décideur ; les strates que le réglage dégrade.
- G — Différences appariées, c1 et c2, quatorze paires chacune.
- H — Le carré du ticket 103 en entier, et les trois graines.
- I — Coût d'inférence détaillé.
- J — Le débat sur la langue d'exécution.

---

## 10. Correspondance avec l'article actuel

| Actuel | Devient | Mots actuels → cible |
|---|---|---|
| 0 Abstract | Abstract, tel quel sauf la phrase sur Jev alignée sur le § 5.3 | 320 → 300 |
| 1 Introduction | § 1 | 2 060 → 700 |
| 2 Related work | § 2 | 1 190 → 450 |
| 3 Architecture | § 3 | 2 500 → 450 |
| 4 Evaluation | § 4.1 à 4.3 | 2 630 → 650 |
| 5 Protocol | § 4.4 pour la méthode ; § 5.2 pour ce qu'elle produit ; annexe D pour les textes | 2 740 → 250 + 150 |
| 6 Empirical Evaluation | § 5 | 2 840 → 1 400 |
| 7 Adaptation | § 6, moins la presse | 2 540 → 750 |
| 8 Limitations | § 7.1 et 7.2 | 2 430 → 400 |
| 9 Conclusion | § 7.3 ; ses trois enseignements montent aux § 5.3, 5.4, 7.1 | 950 → 150 |

---

## 11. Ordre de rédaction

1. Attendre le lot A du ticket 103 pour figer le § 5.3 ; **tout le reste s'écrit sans
   l'attendre.**
2. Écrire le § 5 d'abord : c'est lui qui fixe le vocabulaire (consigne R12) et les chiffres que
   les autres sections citent.
3. Puis § 4, § 6, § 3, § 7, § 2, § 1, abstract : de l'intérieur vers l'extérieur, l'introduction
   en dernier, quand on sait ce qu'elle annonce.
4. Chaque section, en français : `verifier_forme.py` puis `--squelette`, puis relecture des
   consignes R3, R6, R7, R8, R12, R13 à la main.
5. Passe anglaise, section par section, depuis le sens (R17) ; `verifier_forme.py` sur l'anglais.
6. Régénérer les `.tex`, compiler, chercher `??`, compter les pages. Vérifier les en-têtes de
   version des `.tex` contre les masters (R18) **avant tout envoi**.
