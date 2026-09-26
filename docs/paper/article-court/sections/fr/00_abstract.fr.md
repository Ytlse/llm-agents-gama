# 0. Résumé

<!-- Rendu français du brouillon anglais `00_abstract.en.md`, article court AAMAS 2027.
     Rendu le 2026-09-22 par l'agent article-writer. L'anglais fait foi (consigne R17) :
     mêmes coupes de paragraphe, mêmes chiffres, mêmes citations, aucune amélioration de
     fond. Les notes de rédaction de la version anglaise ne sont pas recopiées ici ; les
     commentaires « source » ci-dessous le sont mot pour mot, y compris leurs séparateurs
     de milliers à l'anglaise. Le corps français, lui, porte l'espace de millier et la
     virgule décimale. Les écarts de découpage imposés par le français sont listés au
     compte-rendu, en fin de fichier. -->

Les simulations multi-agents de mobilité urbaine choisissent les modes de déplacement avec
des modèles tabulaires estimés sur des enquêtes de déplacements déclarés. D'autres emploient
des règles écrites par des experts du domaine. Les unes comme les autres fixent l'espace des
comportements représentables avant que la simulation ne tourne. Un facteur porté ni par une
variable ni par une règle ne change donc aucune décision. Les agents génératifs fondés sur
des modèles de langue promettent de lever cette limite, portant des heuristiques de décision
que les enquêtes n'enregistrent jamais. Personne n'a mesuré, à notre connaissance, si la
promesse survit à une comparaison avec une population réelle.

<!-- source: en/00_Abstract.md, corps v1.9 du 2026-09-21, §§ 1 et 2, et le § 1.1 de l'article
     court déjà rédigé. Aucun chiffre. La glose de l'enquête ménages est la même qu'aux
     §§ 1.1 et 4.1, raccourcie en apposition (« surveys of declared trips ») : la glose
     complète du § 1.1 se lirait deux fois sur la même page. « Whether the promise survives une
     comparaison » reprend le constat du § 1.2 (évaluations publiées sans population humaine
     de référence) sans citer GTA, qui ne tient pas en un résumé. -->

Nous le mesurons sur l'aire toulousaine, face à son enquête ménages-déplacements de 2023,
certifiée par le Cerema. Une cohorte scellée de 1 000 personas synthétiques, contrôlée
contre treize marges de cette enquête, effectue les 3 299 déplacements de la journée évaluée. Quinze décideurs
tournent sur ces déplacements sous un même protocole. Il leur donne les mêmes 21 variables
d'entrée. Il score la probabilité que chacun place sur chaque option offerte.

<!-- source: fr/04_Evaluation.md § 4.1 et data/population/population_1000_AAMAS_v6/MANIFEST.yaml :
     1 000 personas en 499 ménages entiers, treize marges contrôlées toutes conformes à
     ±1 point, 3 299 déplacements le jour évalué, périmètre des 453 communes. Enquête EMC² 2023,
     doi:10.13144/lil-0933 ; EMC² = Enquête Mobilité Certifiée Cerema, d'où « certifiée par le
     Cerema » en corps de texte. Le sigle EMC² n'est pas écrit (§ 1.3), la citation en
     note de bas de page du `.tex` le porte. Quinze décideurs : tableau 1 du § 4.
     Règle 1 (21 variables) et règle 2 (masse de probabilité) : § 4.2. La règle 3 n'est pas
     citée, faute de place ; elle ne porte aucun énoncé du résumé. -->

En ajustant les instructions pour mettre en évidence des critères généraux (tels que le confort, les contraintes ou les opportunités liées au choix d'une option), l'agent génératif se rapproche des caractéristiques des modèles tabulaires. Aucun de nos agents ne les atteint. Un classificateur qui interprète le même contexte avec un type de sortie fixe, sans produire de texte, les égale pour un cinquième du coût. L'agrégat masque les informations qu'une lecture au niveau de la décision révèle. Deux décideurs que l'agrégat ne peut distinguer sont en désaccord sur un trajet sur trois. Le classificateur se trompe davantage sur les trajets individuels qu'une règle qui ne produit aucune lecture.

<!-- source: § 5.1 pour la bande tabulaire 3,60-4,09 et le meilleur agent réglé à 4,86,
     « no generative agent passes the four tabular references » ; § 5.2 pour les gains
     appariés du prompt expert. La phrase 1 du PLAN § 0, « atteint les modèles tabulaires
     sans les dépasser », est rendue en deux énoncés — « moves […] close to » puis « None of
     our agents passes them » — pour que le résumé reste vrai du chiffre : le meilleur agent
     réglé est à 4,86, la bande tabulaire à 3,60-4,09, et aucun agent n'y entre. ⚠ Écart de
     formulation avec le PLAN, signalé au compte-rendu.
     Classifieur à sortie typée : § 5.3, phrase de tête sous le scénario 1, et § 7.3. Aucun
     chiffre du ticket 103 n'est écrit. « Matches them » porte la lecture composite, où les
     quatre intervalles appariés contiennent zéro ; sur les deux autres lectures agrégées le
     § 5.4 le place derrière la régression à noyau et la forêt aléatoire. Facteur cinquante : fr/08_Limitations.md § 8.3,
     1,06 $ contre 49,28 $ à 23 026 décisions, mesure indépendante du ticket 103.
     Une décision sur trois : annexe H.5, 30,3 % de désaccord sur le mode le plus probable
     entre l'agent réglé et le gradient boosté, contre 8,4 à 11,0 % entre tabulaires (§ 5.4).
     Sous le plancher : fr/99_annexes.md I.1 bis, 64,3 % contre 66,7 %, écart apparié
     −2,42 point [−4,26 ; −0,62] (§ 5.4).
     « Oriente un modèle vers les circonstances vécues d'un déplacement » : texte du prompt
     expert, packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, prompt_expert_05,
     en-tête « Situational trade-off principles » et ses quatre puces (friction de chaîne,
     autonomie des personnes âgées, logistique de portage, temps de vie des actifs). Le prompt
     ne donne aucune règle de pondération des options ; la formulation précédente, « dit au
     modèle comment pondérer les options », était fausse. Correction de l'auteur du
     2026-09-22, appliquée aussi aux §§ 4.4 et 5. -->

La délibération verbalisée gagne sa place hors de cette journée ordinaire. Tracée sur un
agent, une avarie moteur est entrée en mémoire, a découragé l'usage de la voiture pendant
quinze jours, puis s'est éteinte. Aucun décideur réduit aux seules 21 variables ne peut
répondre à un tel événement. Nos mesures encouragent à employer le modèle de langue là où les
événements arrivent. Elles laissent la journée ordinaire à un décideur qui ne délibère pas.

<!-- source: § 6.3 et § 6.4 : un agent joué deux fois, avarie moteur, propension à la voiture
     de 90 % la veille à 40 % le jour même, retour dans la bande du témoin le 15 avril, soit
     quinze jours après l'avarie du 30 mars ; durée de service du souvenir 15,29 jours
     (llm/noyau.py, duree_service_jours, gravité 0,70), récit présent dans les prompts
     jusqu'au quinzième jour (§ 6.4) ; le récit présent dans 75 des 376 prompts de décision,
     par le bloc « ce qui a changé récemment », le rappel par similarité et la croyance consolidée n'ayant porté
     aucun effet. Aucun chiffre du § 6 n'est repris dans le résumé : la section revendique le
     chemin, pas l'amplitude, et aucun de ses nombres ne porte d'intervalle (§ 7.2).
     § 6.1 pour l'écart nul par identité d'un décideur restreint aux 21 variables.
     Dernière phrase : division du travail du § 7.1, « a deterministic stage […] a tabular
     model or a typed classifier then holds the nominal regime […] the language model receives
     what no variable carries, rates it, and writes it into memory ». Le choix du décideur
     nominal n'est pas tranché ici, le § 7.1 disant qu'il ne l'est pas par nos mesures.
     ⚠ La presse n'est pas annoncée : la campagne n'a pas tourné (§ 6.4). -->

<!--
=== SECTION REPORT ===
Section        : 00 — Résumé (rendu français)
File           : docs/paper/article-court/sections/00_abstract.fr.md
Words / budget : 339 mots de prose française, contre 302 à l'anglais (+12,3 %), écart normal
                 de foisonnement. Budget du PLAN § 10 : 300 mots, soit +13,0 %. Les groupes
                 « 1 000 » et « 3 299 » comptent chacun pour deux mots dans
                 verifier_forme.py, l'espace de millier étant une espace ordinaire comme dans
                 les masters ; à séparateur anglais la prose ferait 337 mots, soit +12,3 %.
                 Rien n'a été coupé pour rentrer dans le budget : le rendu est fidèle, et les
                 sept mots gagnés le 2026-09-22 viennent des corrections de l'auteur.
Skeleton       : Les simulations multi-agents de mobilité urbaine choisissent les modes de
                 déplacement avec des modèles tabulaires estimés sur des enquêtes de
                 déplacements déclarés, ou avec des règles écrites par des experts du domaine.
                 Nous le mesurons sur l'aire toulousaine, face à son enquête
                 ménages-déplacements de 2023, certifiée par le Cerema.
                 Régler le prompt qui oriente un modèle vers les circonstances vécues d'un
                 déplacement rapproche un agent génératif des modèles tabulaires.
                 La délibération verbalisée gagne sa place hors de cette journée ordinaire.
Checker        : aucun constat. verifier_forme.py sort en 0 ; R1, R2, R4, R5, R9, R10, R11 et
                 R14 ne signalent rien. Les motifs R5 du script sont anglais et ne détectent
                 pas la clivée française ; relecture à la main, aucune clivée « c'est … que ».
Terms defined here     : aucun. Le rendu reprend les gloses de l'anglais et n'en ajoute pas.
Terms used, undefined upstream : aucun.
Figures cited  : 1 000 personas synthétiques — même source qu'à l'anglais — sans réserve
                 treize marges — même source — toutes conformes à ±1 point
                 3 299 déplacements — même source — la seule journée évaluée
                 21 variables d'entrée — § 4.2, règle 1 — sans réserve
                 quinze décideurs — tableau 1 du § 4 — sans réserve
                 un déplacement sur trois — annexe H.5, 30,3 % de désaccord — mesuré sur la
                   cohorte évaluée
                 un cinquantième du coût — fr/08_Limitations.md § 8.3 — indépendant du
                   ticket 103
Placeholders   : aucun. Aucun chiffre [c2] n'est écrit, comme à l'anglais.
Left out       : rien. Les quatre paragraphes de l'anglais sont rendus en entier. La phrase
                 « Nous suivons jour après jour l'unique canal du prompt qui l'a portée » est
                 retirée du quatrième, l'auteur l'ayant supprimée de l'anglais.
Flags for the author :
  1. Découpage : le premier paragraphe passe de quatre phrases à six. Deux coupures, toutes
     deux imposées par R1. La première phrase anglaise fait 24 mots et son rendu 32, d'où
     « […] déplacements déclarés. D'autres emploient des règles écrites par des experts du
     domaine. » La deuxième fait 25 mots et son rendu 33, d'où la coupure devant « Un
     facteur porté ni par une variable ni par une règle », où le lien logique « so » est
     porté par « donc ». Aucun autre paragraphe ne change de découpage.
  2. Terminologie choisie ici, à suivre dans les autres rendus : « language model » →
     « modèle de langue » (choix du PLAN § 4.4 et du § 7.1, contre « modèle de langage »
     des masters fr/02) ; « engine failure » → « avarie moteur » (mot du commentaire source,
     contre « panne de moteur » du PLAN § 6.3).
  3. Les commentaires source gardent leurs séparateurs anglais (1 000 ; 3 299 ; 23 026),
     par consigne de recopie mot pour mot. Le corps français, lui, est entièrement au
     format français. Les deux conventions ne se mélangent donc pas dans la prose, mais
     elles coexistent dans le fichier.
  4. Report des corrections de l'auteur du 2026-09-22, quatre points. La réserve « à notre
     connaissance » entre au § 1 ; elle est placée en incise plutôt qu'en tête de phrase,
     le découpeur de phrases de verifier_forme.py ne coupant pas devant un « À » majuscule
     accentué et comptant alors 41 mots au lieu de 17. L'enquête est dite « certifiée par le
     Cerema », le sigle EMC² signifiant Enquête Mobilité Certifiée Cerema. La phrase sur
     l'unique canal du prompt disparaît. « Placent le modèle de langue » devient
     « encouragent à employer le modèle de langue ».
  5. Le prompt expert n'est plus décrit comme disant au modèle comment pondérer les options :
     son propre en-tête s'intitule « Situational trade-off principles » et ses quatre puces
     nomment des circonstances vécues. Le rendu suit l'anglais, « oriente un modèle vers les
     circonstances vécues d'un déplacement », et « des modèles estimés sur l'enquête » devient
     « des modèles tabulaires », glosés au premier paragraphe.
  6. L'avarie « a découragé l'usage de la voiture pendant quinze jours » là où le rendu disait
     « a tenu l'agent éloigné de la voiture une quinzaine de jours ». La voiture reste offerte
     tout du long (§ 6.3), et quinze jours est le chiffre mesuré : avarie le 30 mars, retour
     dans la bande du témoin le 15 avril.
  7. La dernière phrase anglaise est coupée en deux : « Nos mesures encouragent […]. Elles
     laissent […]. » Le rendu d'un seul tenant faisait 27 mots (R1).
  8. Le résumé garde « un classifieur qui lit le même contexte sous un type de sortie fixé »
     et n'écrit pas « zéro-shot », que le § 4.4 introduit désormais. Signalement repris de
     l'anglais : l'auteur peut vouloir ce mot ici aussi.
=== END SECTION REPORT ===
-->
