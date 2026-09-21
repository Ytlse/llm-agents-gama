# Résumé — GAMA Days

**Document :** résumé soumis aux GAMA Days. **La source LaTeX [`GAMA_DAYS_ABSTRACT_EN_TEX.md`](GAMA_DAYS_ABSTRACT_EN_TEX.md) fait référence**, pour le texte comme pour le décompte ; ce fichier et le miroir anglais [`GAMA_DAYS_ABSTRACT_EN.md`](GAMA_DAYS_ABSTRACT_EN.md) s'alignent dessus.
**Version :** `v2.3` (21 septembre 2026) — le dernier paragraphe devient celui du tuteur dans sa forme finale, repris de la source LaTeX. **Ce que vaut le modèle de langage est désormais énoncé**, là où la version précédente disait seulement qu'il valait ailleurs : décrire des choix modaux complexes, en circonstance imprévue surtout, ce que ne permettent ni les modèles à règles ni les enquêtes ménages-déplacements statiques. L'architecture hybride découle de cet énoncé au lieu de le côtoyer. **La phrase de clôture sur GAMA disparaît :** le résumé ne nomme plus la plateforme en dehors du § 2, où la simulation est construite avec elle. Le corps fait 497 mots, quatre paragraphes, deux notes.
**Version antérieure :** `v2.2` (21 septembre 2026) — reprise de la révision du tuteur sur le cadrage et les résultats : l'énoncé de difficulté à l'échelle d'une ville, les facteurs objectifs face aux subjectifs, les agents qui adaptent sans règle explicite, et le paragraphe de résultats dépouillé de ses chiffres. Corps à 493 mots.
**Version antérieure :** `v2.1` (18 septembre 2026) — le dernier paragraphe portait l'argument de la cascade au lieu d'une quasi-parité, et trois références entraient en notes de bas de page.
**Historique :** `v2.0` (17 septembre 2026) refonte des trois derniers paragraphes sur le jeu corrigé du ticket 088 ; `v1.0` (9 septembre 2026) texte soumis, 488 mots. Le détail des versions `v0.1` à `v0.12` est dans le journal en fin de fichier.
**Longueur :** 497 mots, notes exclues. Le décompte se prend sur la source LaTeX, et sur elle seule : `python3 scripts/paper/compter_mots_latex.py docs/paper/gama_days/GAMA_DAYS_ABSTRACT_EN_TEX.md`. La version soumise en faisait 488, la `v2.1` 497, la `v2.2` 493. **Recompter après chaque passe.**
**Convention des tags :** un chiffre laissé en clair se recalcule depuis un fichier du dépôt ; sa source est donnée en commentaire HTML à côté. Aucun emplacement à remplir ne subsiste. Le corps n'en porte plus que deux, les 1 000 individus et les 3 299 déplacements.
**Fichiers liés :** [`fr/01_introduction.md`](../article/fr/01_introduction.md) (dont ce résumé reprend le cadrage), [`fr/06_results.md`](../article/fr/06_results.md) (les mesures), [`fr/08_limits_and_hybrid.md`](../article/fr/08_limits_and_hybrid.md) (le coût d'inférence et la cascade), [`article/fr/00_abstract.md`](../article/fr/00_abstract.md) (le résumé AAMAS, aligné sur cette révision le même jour).

---

## Résumé

Les simulations multi-agents existantes de mobilité urbaine multimodale reposent soit sur des modèles tabulaires estimés depuis des enquêtes ménages-déplacements, soit sur des règles explicites définies par des experts du domaine. Dans les deux cas, l'espace des comportements représentables est fixé a priori : un facteur encodé ni comme variable ni comme règle ne peut influencer aucune décision de l'agent dans la simulation. Or, dans la réalité, le choix d'un mode de transport est multidimensionnel : des facteurs objectifs comme le temps de trajet, l'effort physique, la vitesse et le confort s'entremêlent à des facteurs subjectifs liés à la personnalité et à l'expérience. Intégrer une telle complexité de décision dans une simulation de mobilité multimodale à l'échelle d'une ville est une tâche difficile. Les agents génératifs fondés sur les grands modèles de langage (LLM) promettent de lever cette limite. Nourris de vastes corpus textuels, ils portent des heuristiques de décision que les enquêtes n'enregistrent pas, et savent adapter leurs décisions sans qu'il faille écrire de règles explicites.

Face à une enquête ménages-déplacements certifiée, nous mesurons l'écart de calibration entre ces agents et les modèles estimés sur elle, et nous testons si les agents s'adaptent à des situations qu'aucune variable n'encode. Nous avons construit avec GAMA une simulation de l'aire métropolitaine toulousaine, intégrant les réseaux routier et ferroviaire et trois réseaux de transport en commun. Une population synthétique de 1 000 individus est générée par eqasim <!-- source : data/population/population_1000_AAMAS/MANIFEST.yaml, sceau 1 du 2026-09-02 -->, et les itinéraires alternatifs sont calculés sur les réseaux réels par OpenTripPlanner. La simulation simule une journée réaliste, avec des contraintes réalistes qu'ignore le calculateur d'itinéraires : une voiture disponible là seulement où elle a été laissée, le conducteur nécessaire pour la déplacer, les retours contraints au domicile, l'enchaînement temporel des activités. Chaque habitant y devient un agent génératif : sa règle de choix modal n'est plus écrite dans le modèle de simulation, un grand modèle de langage interrogé par lots la produit à partir du profil de l'agent et des itinéraires réellement offerts, en répartissant 100 % de la décision sur celles-ci.

Sur un jeu de 3 299 déplacements <!-- source : data/population/population_1000_AAMAS/MANIFEST.yaml, sceau 1 -->, nous comparons les résultats de nos agents génératifs à ceux de systèmes classiques fondés sur des règles rigides ou sur des données tabulaires. En situation connue (là où l'espace des comportements représentables est défini a priori), les agents génératifs produisent des résultats très proches des modèles traditionnels, à un léger écart près. Leur véritable force apparaît en circonstance imprévue, tel un article de presse signalant des punaises de lit dans le métro, qui influence les décisions des agents. Nous observons une évolution de leurs choix dans le temps, ainsi que leur capacité à réduire progressivement l'impact de cette information, une adaptabilité que les modèles classiques ne savent pas reproduire.

Chaque décision se paie en inférence, et sur une journée ordinaire, la représentativité des agents génératifs ne justifie pas la dépense : les modèles tabulaires font aussi bien, un peu mieux même, gratuitement et sans délai. Le modèle de langage vaut pour décrire des choix modaux complexes, en circonstance imprévue surtout. Les modèles à règles et les enquêtes ménages-déplacements statiques ne le permettent pas. Cela ouvre en outre une voie vers une architecture hybride : le modèle tabulaire tiendrait le régime nominal, tandis que le modèle de langage, aligné sur les choix des habitants, jugerait du moment de prendre la main et déciderait depuis la personnalité de chacun.

---

## Les deux notes de bas de page

Elles ne vivent que dans le source LaTeX, et ne comptent pas dans la longueur. Chacune sort en
bas de la page où tombe son appel, numérotée automatiquement ; il n'y a rien à placer à la main.

1. **L'enquête**, sur « une enquête ménages-déplacements certifiée » — le rapport publié et les
   microdonnées, sous la forme de citation qu'impose le diffuseur : *Enquête Ménages
   Déplacements (EMD), Toulouse / Grande agglomération toulousaine — 2023, CEREMA, Syndicat
   mixte des transports en commun de l'agglomération toulousaine (producteurs), PROGEDO-ADISP
   (diffuseur)*, suivie du lien vers le rapport final de 68 pages
   ([aua-toulouse.org](https://www.aua-toulouse.org/wp-content/uploads/2024/05/Rapport-final-68-pages-Enquete-mobilite-2023-Bassin-de-vie-toulousain.pdf)).
   Les noms propres restent en français ; le tuteur a remis « producteurs » et « diffuseur » en
   français là où la `v2.1` employait les étiquettes anglaises standard `producers` et
   `distributor`. À vérifier auprès du diffuseur, qui impose la forme de la citation.
2. **Liu, Yang & Yin**, sur « architecture hybride » — *Toward LLM-agent-based modeling of
   transportation systems: a conceptual framework*, arXiv:2412.06681, où l'hybridation est
   proposée comme stratégie d'intégration à court terme.

**Les deux notes retirées.** *GTA: Generative Traffic Agents* (Lämmer, Colley & Ebel, CHI '26,
doi 10.1145/3772318.3790772) et *Evaluating large language models for decision-making in
agent-based urban mobility simulations* (arXiv:2607.02716) accrochaient une phrase qui n'existe
plus, celle qui situait ce travail face aux systèmes publiés. Elles sont disponibles si la
phrase revient ; en l'état, le résumé ne se compare plus à personne.

**À vérifier à la première compilation.** Trois choses, toutes visibles sur le PDF. Les
`\footnote` posées dans l'environnement `abstract` sont avalées par certaines classes, la note
partant alors dans le vide : si `gamadays.cls` fait cela, le remède tient en deux commandes,
`\footnotemark` dans le résumé et `\footnotetext` juste après. Le lien du rapport passe par
`\url`, d'où le `\usepackage{url}` ajouté au préambule. Et la note 1 porte des accents dans le
corps du document : avec un moteur récent (pdfLaTeX depuis 2018, LuaLaTeX, XeLaTeX) c'est
acquis, avec une installation ancienne il faut `\usepackage[utf8]{inputenc}`.

---

## Deux détails à remonter au tuteur

Aucun n'est corrigé ici : la source LaTeX est la sienne, et ces deux points se tranchent avec lui.

1. **« behaviors » contre « behaviours »** dans le même texte. Le § 1 écrit `behaviours`, le § 3
   `behaviors`. Une orthographe à choisir.
2. **Un trait d'union à la place d'un tiret**, au § 3 : `this information-an adaptability`. Sur
   le PDF le mot paraîtra soudé.

**Deux points réglés au passage.** Le collage de la `v2.3` avait emporté le `\end{abstract}` avec
l'ancien paragraphe : le compteur ne trouvait plus l'environnement et le document n'aurait pas
compilé. Il est remis. Le bloc de commentaires en tête du source, qui annonçait encore 497 mots
et quatre notes et listait des chiffres sortis du texte, suit maintenant ce que le corps dit.

---

## Ce que dit le dépôt aujourd'hui

Mesures du 17 septembre 2026, sur le jeu corrigé du ticket 088, tous les décideurs rejoués sur la même cohorte scellée de 1 000 personas. La ligne en gras est celle dont le résumé parle : `gemini-3.5-flash-lite` sous le prompt expert de référence `prompt_expert_05`, température 0.

| Décideur | Composite EMD/JSD | L1 parts globales | Voiture | Marche | TC | Vélo |
|---|---:|---:|---:|---:|---:|---:|
| Cible EMC² 2023 | — | — | 56,7 % | 26,8 % | 12,4 % | 4,1 % |
| Gradient boosté (LightGBM) | **3,60** | 9,49 | 52,8 % | 29,1 % | 14,8 % | 3,3 % |
| Régression logistique à noyau | 3,61 | 6,69 | 54,4 % | 28,9 % | 13,6 % | 3,0 % |
| Logit multinomial | 4,02 | 8,99 | 53,3 % | 27,2 % | 16,4 % | 3,0 % |
| Forêt aléatoire | 4,09 | **5,28** | 56,2 % | 27,6 % | 14,2 % | 2,0 % |
| **Prompt expert, `gemini-3.5-flash-lite`** | **4,86** | **13,85** | **52,3 %** | **24,2 %** | **16,6 %** | **6,8 %** |
| Prompt minimal, `gemini-3.5-flash-lite` | 7,02 | 24,08 | 47,4 % | 24,0 % | 20,9 % | 7,6 % |
| Prompt expert, `mistral-large-2512` | 7,63 | 26,64 | 43,4 % | 29,3 % | 19,2 % | 8,1 % |
| Prompt expert, `gemini-3.1-flash-lite` | 8,98 | 31,25 | 46,2 % | 21,7 % | 24,8 % | 7,4 % |
| Prompt minimal, `gemini-3.1-flash-lite` | 12,38 | 39,88 | 44,1 % | 19,5 % | 28,8 % | 7,7 % |
| Prompt minimal, `mistral-large-2512` | 14,75 | 44,71 | 36,7 % | 24,4 % | 30,6 % | 8,2 % |
| Durée minimale | 26,97 | 53,62 | — | — | — | — |
| A priori empirique, toujours la voiture | 30,73 | 58,00 | — | — | — | — |
| Tirage uniforme | 50,16 | 86,80 | — | — | — | — |

<!-- sources : composites et L1, docs/paper/article/fr/06_results.md § 6.1 ; parts modales, annexe H.3 ; trace docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ -->

Quatre enseignements pour la rédaction et pour la présentation orale.

**Ce que « très proches, à un léger écart près » recouvre.** L'écart **apparié** à gradient boosting vaut 1,35 point [+0,28 ; +2,47], et il n'exclut pas zéro face à la forêt aléatoire (+0,94 [−0,06 ; +1,98]) ni au logit multinomial (+0,96 [−0,18 ; +2,17]). Le résumé ne chiffre plus rien depuis la révision du tuteur ; à l'oral, c'est ce qui autorise « au niveau de deux des quatre » et interdit « au niveau des quatre ».

Le calage agrégé ne descend pas jusqu'au déplacement : l'agent et gradient boosting désignent un mode le plus probable différent pour 30,3 % des déplacements, contre 8,4 à 11,0 % entre méthodes tabulaires (§ 6.4). Ce chiffre n'est pas dans le résumé ; **c'est le meilleur argument pour la perspective hybride** et il doit figurer dans la présentation.

Le biais résiduel tient dans deux modes minoritaires, les transports collectifs (16,6 % contre 12,4 %) et le vélo (6,8 % contre 4,1 %), la marche étant revenue à 24,2 % contre 26,8 %.

Une journée simulée sur 1 000 habitants consomme 3 millions de tokens, mémoire désactivée, contre zéro pour un modèle tabulaire (§ 8.3). <!-- l'erratum du 2026-09-21 ramène ce chiffre de 23 à 3 millions : la mesure précédente agrégeait par requête HTTP et non par décision ; source docs/traces/2026-09-21_13-10_cout_jev_vs_gemini/ --> Le résumé ne donne pas ce chiffre, il n'en garde que le motif : « chaque décision se paie en inférence ».

---

## Ce qui reste à trancher

1. **Format.** Classe `gamadays`, titre, auteurs, mots-clés, figure d'architecture, matériel additionnel, aucune bibliographie : les deux références du texte sont portées par des notes de bas de page. Le corps fait 493 mots, comptés sur la source LaTeX, soit cinq de plus que la version soumise en `v1.0`.
2. **Les références.** Le résumé porte les siennes en **notes de bas de page**, qui ne comptent pas dans la longueur. GTA et Alves et al. sont sorties avec la phrase qui les accrochait ; `taillandier2019gama`, `horl2021eqasim` et `park2023generative` tiendraient au même prix, et `park2023generative` est le seul dont le corps emploie déjà le terme sans le créditer (« agents génératifs »). **Deux réserves :** personne n'a vérifié que les organisateurs excluent les notes du décompte, ni que `gamadays.cls` accepte un `thebibliography` si l'on préférait une vraie bibliographie.
3. **La décroissance de l'effet de presse n'existe toujours pas comme mesure.** L'article mesure l'hystérésis après un choc vécu (tickets 041 et 063) et l'effet de presse dans une campagne séparée (ticket 064). Le retour aux habitudes après une annonce n'est décrit nulle part, ni comme protocole ni comme mesure. Le résumé l'annonce pourtant — « une évolution de leurs choix dans le temps » et « réduire progressivement l'impact de cette information » — et c'est une expérience à écrire avant la présentation.
4. **Le degré de détail sur la plateforme.** La figure d'architecture porte une partie de cette charge. Pour l'oral, nommer les briques (service de décision, passerelle multi-fournisseurs, cache d'itinéraires, registre d'expériences) rendrait le travail directement réutilisable.
5. **Tenue des trois fichiers.** Le source LaTeX mène désormais ; le français et l'anglais le suivent. Deux dépendances vivent hors du dépôt : la classe `gamadays.cls` et l'image `architecture_GAMA_Agents.jpg`.

---

## Journal

- 21 septembre 2026 — `v2.2`. Reprise de la révision du tuteur, qui fait désormais référence. Le cadrage gagne l'énoncé de difficulté et l'adaptation sans règle explicite, les facteurs objectifs sont nommés face aux subjectifs, et le paragraphe de résultats abandonne ses chiffres pour « très proches des modèles traditionnels, à un léger écart près ». Les 21 variables, les 39 203 déplacements et la comparaison aux systèmes publiés quittent le texte, emportant deux des quatre notes. Le corps passe de 497 à 493 mots. Le coût d'inférence du tableau de mesures passe de 23 à 3 millions de tokens, erratum du § 8.3. Le résumé AAMAS est aligné le même jour.

- 18 septembre 2026 — `v2.1`. Le paragraphe de résultats nommait une colonne de mesure où l'agent est dernier ; il nomme l'enquête. Le paragraphe final ne plaide plus la quasi-parité, qui rendait l'agent redondant : le tabulaire tient le quotidien parce qu'il fait aussi bien pour rien, le modèle de langue tient la rupture parce qu'il est le seul à la voir et à décider depuis la personnalité du persona. Le décompte de mots se prend sur le LaTeX, notes exclues, par `scripts/paper/compter_mots_latex.py` : 497 mots, quatre notes exclues.

- 17 septembre 2026 — `v2.0`. Les trois derniers paragraphes refaits sur le jeu corrigé. Le § 5 perd le score composite, les parts modales et le plancher « toujours la voiture » : un lecteur du seul résumé n'a pas de quoi interpréter un composite qu'aucune phrase ne définit, et le plancher servait à situer un agent qui échouait. Le § 6 remplace l'hystérésis après panne de métro par la décroissance de l'effet de presse, à la demande de l'auteur. Le § 7 passe au conditionnel : l'architecture hybride est une perspective ouverte par ces travaux, pas un dispositif décrit. Le fil rouge devient capacité, prix, répartition.

- 9 septembre 2026 — `v1.0`, version soumise. Dernière phrase resserrée par l'auteur en « la part des reports modaux et le taux de réadoption ». Le fichier LaTeX du dépôt cesse d'être un fragment : il porte le document complet envoyé, classe `gamadays`, titre, auteurs, mots-clés, figure d'architecture et lien de matériel additionnel, ce qui garde le dépôt et la soumission identiques.

- 9 septembre 2026 — `v0.12`. Relecture du PDF compilé. Les deux emplacements ⟨xx⟩ étaient visibles dans le document soumis, sur les deux grandeurs mêmes qui portent la moitié « opportunités » du titre ; la phrase les nomme désormais sans les chiffrer. La note de provenance, raccourcie par l'auteur, avait perdu son verbe : corrigée au strict minimum, « on a sealed cohort » au lieu de « , set of a sealed cohort ».

- 9 septembre 2026 — `v0.11`. La phrase de résultat ne justifie plus le choix du composite, elle le définit : un écart aux distributions observées, à minimiser. Le lecteur sait donc dans quel sens lire 12,6 sans avoir à consulter la note, et la raison d'être de la métrique, l'impossibilité de compenser une erreur d'une strate par une autre, reste disponible en note pour qui la cherche.

- 9 septembre 2026 — `v0.1` à `v0.10`. Première mise au propre du brouillon, texte tourné vers la communauté GAMA, resserrement du paragraphe 3, création du miroir anglais, échelle unitaire réservée à AAMAS, vocabulaire d'agent génératif rétabli, apport propre de GAMA énoncé, chiffres renseignés, création de la version Overleaf, dix-neuf mots retirés, passage au score composite.
