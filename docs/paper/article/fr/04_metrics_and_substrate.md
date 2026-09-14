# 4. Métriques et socle d'évaluation

<!-- Dernière mise à jour : 2026-09-11 -->

**Document :** chapitre 4 de l'article AAMAS 2027, **première rédaction en français** — texte neuf, et non l'extrait du manuscrit qui occupait ce fichier (`brouillon v0`, § 2 Étape 0 du `MANUSCRIT_DETAILLE_2026.md` `v1.6`, figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md)). Le maître anglais [`en/04_metrics_and_substrate.md`](../en/04_metrics_and_substrate.md) et le rendu LaTeX seront écrits après validation de ce texte ; la parité ne s'applique donc pas encore.
**Statut :** `brouillon v0.8` (11 septembre 2026) — coupes de l'auteur. La section 4.3 tombe à trois phrases : le cas du repli disparaît (une non-réponse est redemandée, pas comptée), la coupe au jour simulé et celle des tentatives sont retirées comme inutiles au lecteur, la convention sur les itinéraires uniques part au [ticket 047](../../../tickets/ticket_047_offre_a_mode_unique_ce_qui_compte_comme_decision.md) parce qu'elle apportait plus d'ambiguïté que de clarté, et les trois cas non imputables du volet tabulaire sortent comme anecdotiques. En 4.5, le développement « ce que ce tableau établit et ce qu'il n'établit pas » est supprimé. La section 4.6 sur le dimensionnement est **supprimée** faute de pages — il en reste une phrase à la fin de 4.5, qui renvoie à la note de dimensionnement du dépôt. Le chapitre couvre désormais exactement ce que la section 1.4 lui annonce : les métriques, les trois règles, le contrôle démographique. `brouillon v0.7` (même jour) — relecture de l'auteur, quatre points. La distance de transport optimal n'est plus justifiée, seulement définie. La règle des deux lectures porte une note de vérification de fin de projet. Le paragraphe « aucun scalaire ne classe » ne cite plus le résultat du témoin — c'est une mesure, elle vit en 4.4 — et ne garde que le principe de lecture par axe. Et le renvoi au « contrat » nomme la contribution C1 dont il vient, le mot n'étant pas parlant sans elle. `brouillon v0.6` (même jour) — passe de fond demandée par l'auteur. **Plus aucun chiffre mesuré n'est écrit en clair** : les mesures ne sont pas terminées et peuvent bouger, tout résultat est un emplacement **[xx]**. Seules restent en clair les constantes de conception (21 variables, quatre modes, six itinéraires au plus, N = 1 000, borne d'équivalence de 1 point, 453 communes). Par ailleurs : les deux divergences du composite sont écrites et justifiées face aux travaux comparables ; les nats sont définis ; la règle de lecture masse / mode le plus probable est reformulée autour du tirage et de sa source ; la liste des 21 variables part en annexe ; la section sur le périmètre de mesure est resserrée, son raisonnement partant au [ticket 047](../../../tickets/ticket_047_offre_a_mode_unique_ce_qui_compte_comme_decision.md) ; le socle ne parle plus que d'**une** cohorte, les versions antérieures étant archivées ; et la section 4.7 sur la convention d'accès aux données est retirée — la convention s'applique, elle ne se raconte pas. `brouillon v0.5` (même jour) — le chapitre décrivait la donnée d'enquête sans dire à quelles conditions elle est détenue. La convention `lil-1750` de Quetelet-Progedo-Diffusion, recopiée dans [`../../sources/ENGAGEMENT_DONNEES_EMC2.md`](../../sources/ENGAGEMENT_DONNEES_EMC2.md), entre au texte en section 4.7 : usage de recherche, non-cession, citation selon le modèle annexé, information du diffuseur, stockage chiffré, destruction en fin de travaux. Ce qui en découle pour le matériel supplémentaire y est dit, et le millésime cité est **2023** (la notification de diffusion portait « 2013 », corrigé par l'auteur le même jour). `brouillon v0.4` (11 septembre 2026) — la section 4.3 disait « écartées du score » sans dire de quel score. Arbitrage de l'auteur : un déplacement contraint est un fait de la journée, il entre dans les parts modales et sort des seuls termes d'accord ; son compte, qui dépend des choix antérieurs du décideur, se publie à côté des parts. `brouillon v0.3` (même jour) — la règle 1 du contrat disait que les trois décideurs reçoivent « les mêmes 21 variables ». Vérifié dans le code : l'agent reçoit en plus l'agenda de sa journée, la météo des tranches à venir et sa mémoire (`persona.py`, champs ajoutés pour l'anticipation de la chaîne). La règle dit désormais ce qui est vrai, et pose le surplus comme objet de la comparaison plutôt que comme une parité qu'il faudrait rétablir. ⚠ La même correction reste à porter en section 1.3 du chapitre 1. `brouillon v0.2` (même jour) — la régression logistique à noyau entre dans le tableau des références (ticket 043 estimé le même jour) : l'emplacement à remplir devient un chiffre, et le texte dit ce que la quatrième famille change — aucune ne domine sur les trois axes, le plafond de l'ablation reste non désigné. `brouillon v0.1` (même jour) — rédigé dans l'ordre décidé le même jour, le français d'abord, sur le modèle du chapitre 3. Trois chiffres du brouillon antérieur ne survivent pas au recoupement dans le dépôt, et le texte les corrige : la cohorte scellée est la **v5** et non la v1 citée en 1.3 ni la v3 citée par le brouillon ; le compte de déplacements suit la chaîne **cyclique** (3 299 et non 2 693) ; l'effectif efficace est recalculé (≈ 1 620 et non 1 750). Le vocabulaire « Tier 1 / 2 / 3 » disparaît au profit des trois degrés de certification de SILICA.
**Conséquence tranchée sur le chapitre 1 :** la section 1.3 décrivait encore la cohorte v1 — six marges, vivier de 5 063 personnes, 2 693 déplacements, sha256 `f67b0777…`. Elle est réalignée sur la v5 le même jour, chapitre 1 en `v0.19` dans les trois arbres ; écart consigné au journal de [`../plan/README.md`](../plan/README.md).
**Place dans l'article :** section 4 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).
**Convention des tags :** **[xx]** est un emplacement à remplir quand la mesure sera close ; sa source est donnée en commentaire HTML à côté, de sorte que le chiffre se recalcule sans chercher. Tant que les expériences du [ticket 045](../../../tickets/ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md) n'ont pas tourné sur la cohorte en service, **aucun résultat n'est écrit en clair** — un chiffre laissé dans un brouillon finit par être cité.
**Conditions d'accès aux données :** convention `lil-1750` — [`../../sources/ENGAGEMENT_DONNEES_EMC2.md`](../../sources/ENGAGEMENT_DONNEES_EMC2.md). Elle s'**applique** — citation selon le modèle annexé, aucune microdonnée redistribuée, rien d'extrait dans le matériel supplémentaire — et ne fait pas l'objet d'une section du chapitre.
**Sources de mesure :** [`docs/arch/score-synthesis.md`](../../../arch/score-synthesis.md), [`controle-population-jeu-de-test.md`](../../../arch/controle-population-jeu-de-test.md), [`../../methode/JUSTIFICATION_TAILLE_ECHANTILLON.md`](../../methode/JUSTIFICATION_TAILLE_ECHANTILLON.md).

---

## 4.1 Deux échelles, et la lecture qui décide de tout

Une population d'agents s'évalue à deux échelles :

- à l'échelle **agrégée**, la question est la fidélité : la répartition modale produite est-elle celle du territoire ?
- à l'échelle **unitaire**, la question est l'accord décision par décision : ce déplacement-là a-t-il reçu le mode que la personne a déclaré ?

### Ce qui se mesure à l'échelle agrégée

Quatre modes sont scorés : voiture, transports collectifs, marche, vélo. La référence est celle de l'enquête EMC² 2023, dont les parts publiées portent un résidu d'« autres modes » — deux-roues motorisés, taxis — que le périmètre ne score pas ; elles sont renormalisées sur les quatre modes retenus, et la masse écartée de part et d'autre est comptée plutôt que passée sous silence. Cible renormalisée : voiture **[xx]** %, marche **[xx]** %, transports collectifs **[xx]** %, vélo **[xx]** %. <!-- source: scripts/data/population/cerema_values.yaml, parts_modales_2023.global -->

Trois grandeurs sont publiées sur cette échelle, et elles ne répondent pas à la même question.

**L'erreur L1**, somme des écarts absolus de parts, s'exprime en points de pourcentage et se lit sans conversion :

$$L_1 = \sum_{m} \left| \hat{P}_m - P_m^{\text{EMC}^2} \right|$$

**La divergence de Jensen-Shannon**, sur les axes **nominaux** — genre, occupation, motif :

$$\mathrm{JSD}(P \parallel Q) = \tfrac{1}{2}\,\mathrm{KL}(P \parallel M) + \tfrac{1}{2}\,\mathrm{KL}(Q \parallel M), \qquad M = \tfrac{1}{2}(P + Q)$$

Trois propriétés la font préférer à la divergence de Kullback-Leibler dont elle dérive : elle est **symétrique**, donc l'ordre des deux distributions ne change pas le résultat ; elle est **bornée** — au plus 1 bit en base 2 —, donc lisible sans échelle de référence ; et elle est **définie quand une modalité est absente**, là où la KL diverge. Ce dernier point n'est pas théorique : un modèle de langue répond volontiers « 90 / 10 / 0 / 0 », et une métrique qui explose sur un zéro mesure alors sa propre constante de lissage plutôt que la décision. C'est aussi la grandeur que publie le travail le plus proche du nôtre — CityReal rapporte une JSD sur la répartition modale (Bougie, Ye & Watanabe, 2026) —, de sorte que nos chiffres se lisent contre les siens.

**La distance de transport optimal** (*Earth Mover's Distance*, ou Wasserstein-1 sur une droite), sur les axes **ordinaux** — classe d'âge, classe de distance. Pour $K$ classes ordonnées et $F$, $\hat{F}$ les fonctions de répartition cumulées :

$$\mathrm{EMD}(\hat{P}, P) = \sum_{k=1}^{K-1} \left| \hat{F}_k - F_k \right|$$

exprimée en unités de classe : elle compte le déplacement le long de l'ordre.

Le **composite** agrège ces lectures par sous-population — âge, occupation, genre, motif, distance. <!-- source: docs/arch/score-synthesis.md § 2 ; prompt_calibration/calibration/metrics.py -->

### Ce qui se mesure à l'échelle unitaire

L'exactitude, l'entropie croisée, et le rappel et la précision par mode.

L'entropie croisée s'exprime en **nats**, c'est-à-dire en unités de logarithme naturel : un nat vaut $1/\ln 2 \approx 1{,}44$ bit. Comme un nat ne se lit pas intuitivement, nous publions à côté son exponentielle inverse, $\mathrm{GMPCA} = e^{-\mathrm{CEL}}$ — la moyenne géométrique de la probabilité que le modèle accordait au mode réellement observé. Celle-ci **est** une probabilité, et se lit comme telle.

Le rappel par mode n'est pas un raffinement : le vélo pèse **[xx]** % des déplacements, et c'est la classe où toute repondération casse la calibration. <!-- source: scripts/progedo_logit/mode_choice_eval.py, evaluate_proba -->

### La règle de lecture, et pourquoi les deux lectures sont publiées

Un modèle probabiliste possède **deux** parts modales : celle de sa masse de probabilité, et celle de son mode le plus probable. Elles ne disent pas la même chose, et l'écart n'est pas anecdotique — sur le jeu de test scellé, l'oracle passe de **[xx]** à **[xx]** points d'erreur L1 entre les deux lectures, et le logit de **[xx]** à **[xx]**. <!-- source: mode_choice_policy_metrics.json et mnl_model_metrics.json, mode_shares.l1_probability_mass / l1_argmax -->

Notre dispositif ne retient donc pas le mode le plus probable. Nous demandons au modèle de **verbaliser sa distribution** plutôt que de l'échantillonner par répétition — Meister et al. (2024) montrent que les distributions verbalisées s'alignent mieux que les distributions échantillonnées — et la décision de l'agent est un **tirage** dans cette distribution. Retenir le mode le plus probable écraserait la variabilité individuelle : tous les personas d'un même profil partiraient dans le même mode, et la population perdrait précisément ce qu'on lui demande de reproduire.

Le but de publier les deux lectures est qu'**aucune comparaison ne dépende d'une lecture choisie après coup**. La masse est la grandeur scorée, et c'est elle qui se compare à la masse d'un autre modèle probabiliste ; le mode le plus probable est la seule lecture comparable à des décisions dures. Publier la première sans la seconde flatterait tout modèle bien calibré ; publier la seconde sans la première le condamnerait sur une lecture qu'il ne produit jamais. Les deux sont donc rapportées, systématiquement, pour tous les décideurs comparés. <!-- (NOTE — À VÉRIFIER EN FIN DE PROJET) : contrôler que les deux lectures sont effectivement publiées partout où un décideur probabiliste est comparé — tableaux des chapitres 5 et 6 compris. Une règle annoncée au chapitre 4 et tenue à moitié plus loin est pire que pas de règle. -->

**Enfin, aucune de ces grandeurs ne se suffit à elle-même.** Martín-Baos et al. (2023) montrent que l'ordre des modèles de choix modal s'inverse selon la famille d'indicateurs : un modèle peut mener sur les parts agrégées et perdre sur l'exactitude désagrégée. C'est pourquoi les grandeurs ci-dessus sont publiées ensemble et lues **par axe**, jamais résumées en un classement.

## 4.2 Les trois règles du contrat d'évaluation

La première contribution annoncée en 1.3, sous le nom de **contrat d'évaluation**, tient en trois règles. Chacune ferme une manière de biaiser la comparaison entre un agent génératif et un modèle tabulaire, chacune est appliquée par le code et vérifiable dans le dépôt.

**Règle 1 — parité informationnelle sur le déplacement courant.** L'agent, le logit et l'oracle reçoivent les mêmes 21 variables décrivant la personne et le déplacement à décider : douze pour la personne et son ménage, trois pour le contexte, six pour la géométrie. La liste complète est en annexe, et elle est figée dans un fichier de spécification du dépôt — c'est ce même fichier qui construit la matrice de dessin des modèles tabulaires. <!-- source: scripts/progedo_logit/feature_spec.json ; liste reproduite en annexe -->

L'agent reçoit en outre trois choses qu'aucun modèle tabulaire ne peut recevoir : l'**agenda des trajets qui lui restent** avant le retour au domicile, la **météo des tranches horaires à venir**, et sa **mémoire**. <!-- source: mobility_llm/src/mobility_llm/persona.py, champs agenda et day_outlook — « anticipation de la chaîne de la journée » --> Décider en sachant ce que ce choix imposera le soir est précisément la capacité qu'un classifieur trajet par trajet n'a pas. La parité porte donc sur la description du déplacement courant, et le surplus est déclaré.

> **(NOTE — POINT À TRAVAILLER.)** La formulation de ce surplus n'est pas arrêtée. Dire qu'il est « l'objet de la comparaison » règle la question trop vite : il reste qu'un écart mesuré entre l'agent et l'oracle mêle deux causes, la règle de décision et l'horizon d'information, et le texte doit dire laquelle il isole. Examen en cours, [ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md). Aucun chiffre ne se publie sous un contrat dont l'énoncé n'est pas stabilisé.

Deux asymétries encadrent la comparaison, et elles jouent en sens inverse. Sur l'**exposition**, l'oracle a été ajusté sur **[xx]** trajets d'enquête et l'agent n'en a vu aucun : c'est ce qui fait de l'oracle une référence haute plutôt qu'un concurrent. Sur l'**horizon**, l'agent voit sa journée et l'oracle ne voit qu'un trajet : c'est ce que la section 6 mesure, en jouant les références tabulaires deux fois, sous la contrainte de chaîne des véhicules et sans elle.

**Règle 2 — lectures homogènes.** L'agent ne désigne pas un itinéraire : il répartit une masse de probabilité sur les options qui lui sont présentées, six au plus. Cette masse est la grandeur scorée, et elle se compare à la masse du modèle tabulaire ; le mode le plus probable est publié en second, face à l'argmax tabulaire. La décision jouée dans la simulation est un tirage dans cette masse (section 4.1, et chapitre 3, section 3.3). Trois lectures cohabitent donc et ne se mélangent jamais : la masse attendue, le mode tiré, le mode le plus probable.

**Règle 3 — renormalisation sur l'offre.** Le modèle tabulaire prédit sur quatre classes sans savoir ce qui était offert ; l'agent ne choisit que parmi les itinéraires que les calculateurs ont réellement renvoyés. Chaque prédiction tabulaire est donc restreinte aux modes offerts pour ce déplacement, puis renormalisée à 100 %. Les probabilités sont écrites **avant et après** correction : sans le « avant », la renormalisation serait une affirmation invérifiable. Elle n'est pas cosmétique — elle retire **[xx]** points à la part voiture du modèle, qui la surprédit dans sa vision en aveugle. <!-- source: docs/arch/score-synthesis.md, renormalisation_bias du data.json --> Elle suppose l'indépendance des alternatives non pertinentes, hypothèse que la section 8.1 déclare comme limite.

## 4.3 Le périmètre de mesure

N'entre dans un chiffre publié que ce qui porte une **décision modale** : une paire
origine-destination qu'aucun mode ne relie et un déplacement qui n'a pas lieu en sortent. Une
non-réponse du modèle n'est pas non plus une décision — elle est **redemandée**, jamais comptée
comme un choix. Chaque exclusion est comptée, et son compte publié à côté du résultat.

## 4.4 Le socle de référence

**Une seule cohorte est en service.** Les versions antérieures de la population synthétique sont archivées et hors d'usage ; toute mesure de l'article porte sur la cohorte scellée décrite en 4.5, et un chiffre produit sur une autre n'entre pas dans l'article. C'est là que vivent les agents, la simulation et les régimes non tabulés.

Les familles tabulaires, elles, ne s'évaluent pas sur cette cohorte : elles sont ajustées et caractérisées sur les **microdonnées de l'enquête**, dont le jeu de test est scellé et découpé **par ménage** et non par trajet, pour qu'aucun membre d'un ménage d'entraînement ne se retrouve en test. Ce jeu dit qu'un modèle tient ; il ne le fait pas entrer dans la comparaison aux agents, qui a lieu sur la cohorte. <!-- source: mode_choice_policy_metrics.json, split.by = hh_id -->

Les quatre familles sont estimées **à parité stricte** — même fichier de données, même découpage par ménage, mêmes poids de redressement, même encodage, mêmes métriques issues d'un module partagé. Toute entorse à ces cinq points rendrait la colonne illisible.

| Famille de référence | Exactitude | Entropie croisée (nats) | GMPCA | L1 masse | L1 mode le plus probable | Rappel vélo |
|---|---:|---:|---:|---:|---:|---:|
| Oracle supervisé (gradient boosté) | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** |
| Logit multinomial | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** |
| Random forest (témoin, non candidat) | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** |
| Régression logistique à noyau | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** | **[xx]** |

<!-- sources: mode_choice_policy_metrics.json ; mnl_model_metrics.json ; rf_mode_choice_metrics.json (principal.test) ; klr_model_metrics.json ; même jeu de test scellé, métriques pondérées -->

Quatre familles, trois axes, et une conclusion par axe. Sur les **parts agrégées**, les arbres suffisent : le témoin dépasse l'oracle, si bien que l'article ne peut pas attribuer la fidélité des parts au boosting. Sur l'**exactitude désagrégée**, l'avantage se partage. Sur la **classe minoritaire**, le boosting est décisif — le témoin passe sous le logit alors que sa masse vélo est bien calibrée, ce qui est exactement la dissociation que la règle de lecture de 4.1 rend visible.

La quatrième famille comble l'axe que les trois premières laissaient ouvert : la régression logistique à noyau, non linéaire comme le booster et lisse comme le logit, que Martín-Baos et al. (2023) désignent comme le meilleur compromis entre exactitude et plausibilité comportementale. Elle tient la promesse sans la dépasser. <!-- source: scripts/progedo_logit/klr_model_metrics.json ; noyau RBF, approximation de Nyström -->

Aucune famille ne domine donc sur les trois axes à la fois, et **le plafond de référence de l'ablation ne se désigne pas par un scalaire**. Le critère est annoncé ici, avant le chiffre : une famille ne devient la référence haute que si elle domine sur les parts agrégées *et* ne dégrade pas le rappel des modes minoritaires.

Le composite publié, enfin, ne mesure que la fidélité à l'enquête. Deux termes complémentaires sont calculés et publiés à côté — l'accord désagrégé à un modèle de comportement, et la cohérence du **sens** des variations — mais ils portent un **poids nul** : un prompt sélectionné sous un terme mesuré contre un modèle serait ajusté à ce modèle, et non au territoire. Le composite restant linéaire, leur promotion ultérieure serait exacte et rétroactive, sans un seul appel de modèle à repayer. <!-- source: scripts/synthesis/bi_oracle.py -->

## 4.5 La cohorte scellée et son contrôle démographique

La cohorte est un dossier immuable : une population, son empreinte, la règle qui l'a produite, le rapport qui l'a jugée. Elle compte 1 000 personnes réparties en **[xx]** ménages entiers — l'unité de tirage est le ménage, condition sans laquelle les règles de chaîne des véhicules du chapitre 3 n'auraient pas de sens — tirées dans un vivier de **[xx]** personnes produit par la chaîne de synthèse eqasim (Hörl & Balać, 2021) à partir du recensement, des revenus fiscaux et de l'enquête ménages. Le périmètre est celui de l'enquête : les 453 communes du bassin de vie toulousain, délimitées par le polygone communal et non par un rayon. <!-- source: MANIFEST.yaml de la cohorte en service -->

Chaque personne pèse un. La mobilité de la cohorte est celle de ses chaînes d'activités, qui sont **cycliques** — la journée se referme sur le retour au domicile, si bien qu'une chaîne de *k* activités porte *k* déplacements. Elle produit **[xx]** déplacements le jour évalué, soit **[xx]** par personne et **[xx]** par personne mobile, avec **[xx]** % d'immobiles ; l'enquête donne **[xx]**, **[xx]** et **[xx]** %. <!-- source: MANIFEST.yaml, controle.menages_et_mobilite --> Le nombre de décisions réellement scorées est inférieur, et l'écart s'explique par les exclusions de la section 4.3 : **[xx]**.

Treize marges sont contrôlées, chacune avec sa source — une page du rapport publié, ou un recalcul sur les microdonnées de l'enquête gelé dans le dépôt quand le rapport ne publie pas la marge.

| Marge | Base | Source | Écart max | Verdict |
|---|---|---|---:|---|
| Classe d'âge (6 classes) | personne | rapport publié | **[xx]** | conforme |
| Occupation | personne | rapport publié | **[xx]** | conforme |
| Âge quinquennal (15 classes) | personne | microdonnées | **[xx]** | conforme |
| Motorisation | personne | microdonnées | **[xx]** | conforme |
| Motorisation | ménage | rapport publié | **[xx]** | conforme |
| Couronne de résidence | personne | rapport publié | **[xx]** | conforme |
| Couronne × motorisation | personne | microdonnées | **[xx]** | conforme |
| Taille de ménage | personne | microdonnées | **[xx]** | conforme |
| Permis de conduire (18 ans et +) | personne | microdonnées | **[xx]** | conforme |
| Abonnement aux transports collectifs | personne | microdonnées | **[xx]** | conforme |
| Type de logement | personne | microdonnées | **[xx]** | conforme |
| Genre | personne | microdonnées | **[xx]** | conforme |
| Personnes sans déplacement la veille | personne | microdonnées | **[xx]** | conforme |

<!-- source: CONTROLE.md de la cohorte en service ; recalculs cités selon la convention lil-1750 -->

Le test est un **test d'équivalence** marge par marge, avec une borne d'indifférence de 1 point annoncée avant la mesure, complété par l'écart absolu maximal et un $V$ de Cramér comme taille d'effet. Ce n'est pas un raffinement de présentation. Un khi-deux non significatif ne prouve pas la conformité : il échoue à détecter un écart, ce qui n'est pas la même chose, et à mille personnes sa puissance est faible. Un critère de la forme « non-rejet à $p > 0{,}95$ » n'est pas un critère statistique.

Mille personnes, enfin, n'est pas un budget mais un calcul de précision fait avant la mesure : à cet effectif, et compte tenu de la corrélation entre les déplacements d'une même personne, la demi-largeur de l'intervalle de confiance reste sous les biais structurels que l'article cherche à établir, tout en restant au-dessus de l'incertitude propre de l'enquête de référence. Le calcul *ex ante* est détaillé dans la note de dimensionnement du dépôt, et tout intervalle publié est estimé par rééchantillonnage par grappe agent. <!-- source: docs/paper/methode/JUSTIFICATION_TAILLE_ECHANTILLON.md -->

---

### Tickets associés à ce chapitre
- [Ticket 043](../../../tickets/ticket_043_troisieme_famille_regression_logistique_noyau.md) — Troisième famille de référence : régression logistique à noyau
- [Ticket 045](../../../tickets/ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md) — Substrat unique v5 et reconstruction des expériences
- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — L'agent voit sa journée, le modèle tabulaire non : que dit le contrat ?
- [Ticket 047](../../../tickets/ticket_047_offre_a_mode_unique_ce_qui_compte_comme_decision.md) — Offre à mode unique : ce qui compte comme décision
- [Ticket 052](../../../tickets/ticket_052_documentation_cohorte_scellee_v5.md) — Documentation et scellement démographique de la cohorte v5
- [Ticket 053](../../../tickets/ticket_053_acces_donnees_recherche_et_reproductibilite.md) — Modalités d'accès aux données d'enquête pour la recherche et protocole de reproductibilité
