# 7. Implications, limites, conclusion
<!-- Rendu français du brouillon anglais validé, article court AAMAS 2027, PLAN.md § 7.
     Rendu le 2026-09-22 par l'agent article-writer, consigne R17 : l'anglais est la source,
     le français en est le rendu fidèle, à coupes de paragraphes et chiffres identiques.
     Aucun ajout de fond, aucune correction de fond ; les problèmes relevés au rendu vivent
     au compte-rendu. Les commentaires de source sont ceux du fichier anglais, repris mot
     pour mot. Nombres convertis aux usages français : espace fine pour les milliers,
     virgule pour les décimales. -->

Le jour ordinaire et l'événement tracé portent sur la manière de construire un agent de
mobilité, et sur ce que nous ne pouvons pas revendiquer.

## 7.1 Ce que ces résultats disent d'une architecture

Le coût d'une journée simulée fixe l'endroit où la délibération reste abordable. Une journée
de semaine sur 1 000 personas sollicite le modèle de langue 2 108 fois et consomme
3 millions de tokens, mémoire désactivée. L'activation de la mémoire y ajoute quelque
2,5 millions. Au périmètre des 453 communes de l'enquête, une journée simulée demanderait
2,9 millions de sollicitations, pour 2,6 à 4,2 milliards de tokens. Une réponse publiée à ce
coût partage un même appel entre agents comportementalement proches (Chopra et al., 2024).

<!-- source: fr/08_Limitations.md § 8.3 : « une journée de semaine sur 1 000 personas produit
     3 299 déplacements […] la journée de référence en demande 2 108 [sollicitations] […] La
     journée de référence consomme ainsi 3 millions de tokens » (compteurs.json de
     l'exécution 2026-09-15_07_02_03 ; jetons agrégés par décision depuis llm_exchanges.jsonl,
     erratum de la trace du 2026-09-17 corrigé par docs/traces/2026-09-21_13-10_cout_jev_vs_gemini/).
     Mémoire active : « une journée à mémoire active ajouterait environ 2,5 millions de
     tokens » (1,25 consolidation courte et 0,27 auto-réflexion par agent et par jour, mesurées
     sur experiments/archive/2026-09-16_15_58, 5 personas et 11 jours ; rapportées aux 894
     personas mobiles). Périmètre d'enquête : « une journée simulée demanderait 2,9 millions de
     sollicitations […] et de 2,6 à 4,2 milliards de tokens » (1 320 000 habitants de 5 ans et
     plus, 3,30 déplacements par personne, une sollicitation pour 1,5 décision).
     ⚠ Réserve de la source : les grandeurs au périmètre d'enquête sont dérivées, non mesurées.
     Le mot « would » la porte ; les 2 108 sollicitations et les 3 millions de tokens, eux, sont
     mesurés. Sortent, faute de place : les 270 requêtes de la journée, les 370 000 requêtes du
     périmètre, et le mur de débit du décideur typé, qui n'accepte qu'un état par requête.
     Chopra et al. (2024) : clé BibTeX chopra2024limits, « On the limits of agency in
     agent-based models », un appel partagé entre agents comportementalement proches. Renvoyé
     ici par le PLAN § 2.2, qui le sort du § 2.2 et lui accorde une demi-phrase au § 7. Il
     porte l'alternative à la division par régime du paragraphe suivant ; aucune de nos
     mesures ne la teste. -->

Nos mesures suggèrent une division du travail par régime plutôt qu'un seul décideur partout.
Un étage déterministe retire les options qu'une personne ne peut pas prendre, faute de
permis, de véhicule sur place ou d'itinéraire. Un modèle tabulaire ou un classifieur à
sortie typée tient ensuite le régime nominal. Le modèle de langue reçoit ce qu'aucune
variable ne porte et l'écrit en mémoire. Noter la gravité de cet événement est sa tâche dans
la conception actuelle, sans que le cas tracé l'ait exercée (§ 6.2).

<!-- source: fr/08_Limitations.md § 8.4, premier paragraphe : « un premier étage déterministe
     élague les alternatives physiquement ou légalement impossibles, absence de permis,
     véhicule garé ailleurs, absence d'offre ; un second étage tabulaire traite les
     déplacements de routine en régime nominal […] un troisième étage n'appelle le modèle de
     langue que sur rupture ». Le classifieur typé comme second candidat de l'étage nominal :
     même section, cinquième paragraphe. Le modèle de langue reçoit et écrit, et la notation
     de la gravité reste une tâche de conception : formulation imposée par la relecture v1,
     point P1, le cas tracé du § 6.2 n'exerçant pas cette étape.
     ⚠ Le PLAN § 7.1 écrit « un étage tabulaire OU un classifieur typé » sans trancher ; le
     paragraphe suivant dit pourquoi le choix n'est pas tranché par nos mesures. -->

Le second étage impose un choix que nos mesures ne tranchent pas. Un modèle tabulaire tient
les deux échelles, mais il n'existe pas avant l'enquête qui l'ajuste. Le classifieur à sortie
typée se passe d'une telle enquête et atteint pourtant la bande tabulaire sur l'agrégat. Sur
les déplacements individuels, en revanche, il tombe sous le plancher tout-voiture (§ 5.4).
Une architecture qui le placerait à l'étage nominal achèterait la fidélité agrégée à bas coût
et perdrait la fidélité individuelle. Un décideur qui lise le contexte, se passe d'enquête
locale, tienne l'agrégat et batte ce plancher n'existe pas dans nos mesures. Cet article
laisse le problème ouvert. Nous n'estimons pas la part des déplacements qui reviendrait à
chaque étage.

<!-- source: fr/08_Limitations.md § 8.4, cinquième paragraphe : « un modèle tabulaire n'existe
     pas avant l'enquête qui l'ajuste ; le classifieur à sortie typée tient le régime nominal
     sans avoir lu une ligne du territoire qu'il décrit […] Deux réserves l'accompagnent : la
     mesure porte sur un seul territoire, et le § 6.4 montre que la fidélité agrégée de ce
     décideur ne se retrouve pas à l'échelle individuelle. » Chute sous le plancher tout-voiture :
     fr/99_annexes.md I.1 bis, −2,42 point [−4,26 ; −0,62], repris au § 5.4 déjà rédigé.
     Parts de flux non mesurées : même section, troisième paragraphe, « aucun compteur du
     dispositif ne sépare les décisions de routine des décisions de rupture ». Le motif sort du
     texte par la relecture v1, § 9 bis, dernière ligne ; seul le constat reste.
     ⚠ Le PLAN § 7.1 écrit « un décideur qui lise le contexte, tienne l'agrégat et batte la
     constante sur l'individu n'existe pas dans nos mesures ». Pris à la lettre, l'énoncé est
     faux : le gradient boosté lit les 21 variables, tient l'agrégat (3,60) et bat le plancher
     tout-voiture (71,5 % contre 66,7 %). La clause « needs no local survey » est ajoutée ici
     pour que l'énoncé soit vrai ; signalé au compte-rendu.
     Sort, faute de place : la seconde division du travail du § 8.4, où le classifieur décide
     tout et le modèle de langue n'écrit que la mémoire, pour deux dollars la journée contre
     sept ; ces deux montants sont dérivés et non mesurés. -->

## 7.2 Limites

Quatre limites bornent ce que ces mesures permettent d'affirmer. Les références tabulaires
ont lu 39 203 déplacements d'enquête que les agents n'ont pas lus. Aucun résultat ne compare
donc ici deux décideurs à information égale. Notre banc établit ce qu'un classifieur trajet
par trajet ne peut pas faire, et non qu'un agent décide mieux. La règle 3 repose sur
l'indépendance des alternatives non pertinentes, l'hypothèse que retirer un mode
indisponible laisse inchangé le rapport entre deux modes conservés. Trois de nos quatre
références tabulaires ne la garantissent pas. L'erreur que cette hypothèse introduit dans
leurs prédictions renormalisées n'est pas bornée ici. Le chemin tracé au § 6 repose sur un
agent, un événement et une graine, si bien qu'aucun chiffre de cette section ne porte
d'intervalle. Son incident laisse la voiture utilisable, là où une avarie moteur réelle
l'immobiliserait. Notre convention de recherche interdit de céder les microdonnées de
l'enquête, si bien que réestimer nos références tabulaires demande d'obtenir l'enquête aux
mêmes conditions.

<!-- source, limite 1 : fr/08_Limitations.md § 8.2, dernier paragraphe des asymétries :
     « Les quatre méthodes tabulaires ont lu 39 203 déplacements réels de l'enquête locale, et
     l'agent n'en a lu aucun. […] Ce que le dispositif établit est qu'un agent fait quelque
     chose qu'un classifieur trajet par trajet ne peut pas faire, et non qu'il fasse mieux à
     information égale. » Le § 4.2 déjà rédigé déclare l'asymétrie ; la phrase ci-dessus dit ce
     qu'elle interdit de conclure, et ne la redit pas (règle 8).
     source, limite 2 : fr/08_Limitations.md § 8.2, dernière phrase : « la renormalisation […]
     repose sur l'hypothèse d'indépendance des alternatives non pertinentes […] ce que le logit
     multinomial vérifie par construction et que les trois autres méthodes ne garantissent
     pas. » La glose est portée dans la phrase, le terme n'étant défini nulle part en amont.
     source, limite 3 (clause du véhicule) : fr/07_Adaptation.md § 7.2.2, « ce qu'une avarie
     moteur ne produirait pas dans le monde réel » (ticket 079). Phrase déplacée depuis le
     § 6.3 par la relecture v1, § 9 bis, ligne 6.3, qui la veut une seule fois et ici.
     source, limite 3 : fr/07_Adaptation.md, chapeau : « Le chapitre ne prétend à aucun réalisme
     sur l'ampleur ni sur la forme du report. » L'absence d'intervalle est un constat de
     l'agent rédacteur sur la section 6 livrée, qui ne porte aucune dispersion ; signalé au
     compte-rendu.
     source, limite 4 : fr/99_annexes.md, annexe G, convention lil-1750 de
     Quetelet-Progedo-Diffusion, non-cession des microdonnées. Le § 4.1 déjà rédigé dit ce qui
     se diffuse ; la phrase ci-dessus dit ce que la non-diffusion coûte à la reproduction. -->

## 7.3 Conclusion

Cet article établit quatre choses. Sur une cohorte synthétique contrôlée de Toulouse, un
agent génératif calibré atteint les modèles tabulaires estimés sur l'enquête sans les
dépasser. Un classifieur à sortie typée, qui lit le même contexte et n'écrit rien, atteint
la même bande pour un cinquantième du coût. Deux décideurs que l'agrégat ne sépare pas
diffèrent sur un déplacement sur trois, et l'un d'eux tombe sous une règle qui ne regarde
rien. La délibération reçoit un événement non tabulé, l'écrit en mémoire et le laisse
s'éteindre. Rien d'autre ne l'a fait dans nos mesures. Nous montrons par quel canal, sur un
cas tracé de bout en bout.

<!-- source: PLAN § 0, « Ce que le papier établit, en quatre phrases », rendues dans l'ordre.
     Les quatre chiffres qui les portent vivent aux §§ 5.1, 5.3, 5.4 et 6.4 ; la conclusion
     n'en réécrit aucun, par l'exception de la règle 8 (une phrase par résultat).
     ⚠ La deuxième phrase dépend du ticket 103, lot A : elle est écrite sous le scénario 1 et
     ne porte aucun chiffre, le composite hors échantillon du classifieur restant un
     emplacement au § 5.3. Sous le scénario 3 elle sort de la conclusion. -->

Deux questions restent ouvertes. Nous transmettons la recherche du décideur manquant, celui
qui tiendrait les deux échelles sans enquête locale. La campagne de presse, qui porte le même
canal jusqu'à une information que l'agent se contente de lire, n'a pas rendu ses résultats.

<!-- source: le décideur manquant, § 7.1 ci-dessus, reformulé en une phrase ; la campagne de
     presse, fr/07_Adaptation.md § 7.3, cinq articles de la presse toulousaine et vingt signes
     préenregistrés, campagne exp_05a-e non tournée au 2026-09-22. Répétition assumée du
     dernier paragraphe du § 6.4, autorisée par la règle 8 pour la conclusion. -->

<!--
=== SECTION REPORT ===
Section        : 07 — Implications, limites, conclusion
File           : docs/paper/article-court/sections/07_implications.fr.md
Words / budget : 626 / 550 (+13,8 %) — anglais source : 593 mots, écart de rendu +5,6 %
                 (7.1 286/250, 7.2 163/150, 7.3 150/150)
Skeleton       :
  Le jour ordinaire et l'événement tracé portent sur la manière de construire un agent de mobilité, et sur ce que nous ne pouvons pas revendiquer.
  Le coût d'une journée simulée fixe l'endroit où la délibération reste abordable.
  Nos mesures suggèrent une division du travail par régime plutôt qu'un seul décideur partout.
  Le second étage impose un choix que nos mesures ne tranchent pas.
  Quatre limites bornent ce que ces mesures permettent d'affirmer.
  Cet article établit quatre choses.
  Deux questions restent ouvertes.
Checker        : verifier_forme.py sort 0, « Aucune consigne mécanique en faute », dès la
                 première passe. --squelette lu d'une traite : les sept phrases-sujets
                 racontent la section. R5 relu à la main sur le français, qui tolère la
                 clivée : aucune tournure « c'est … que » n'est écrite.
                 Séparateur de milliers : espace simple, convention des masters français.
Terms defined here     : aucun. Une seule glose est portée dans la phrase, celle de
                 l'indépendance des alternatives non pertinentes.
Terms used, undefined upstream : aucun.
Figures cited  : identiques à l'anglais, réserves comprises.
                 2 108 sollicitations et 3 millions de tokens — fr/08_Limitations.md § 8.3 —
                   mesurés.
                 2,5 millions de tokens supplémentaires — même source — dérivés.
                 453 communes, 2,9 millions de sollicitations, 2,6 à 4,2 milliards de tokens —
                   même source — dérivés ; le conditionnel « demanderait » porte la réserve,
                   comme le « would » de l'anglais.
                 39 203 déplacements d'enquête — fr/08_Limitations.md § 8.2 — mesuré.
                 Chute sous le plancher tout-voiture (§ 5.4) — fr/99_annexes.md I.1 bis.
Placeholders   : aucun. Les deux dépendances au ticket 103 signalées au compte-rendu anglais
                 valent pour ce rendu, sans changement.
Left out       : rien de l'anglais.
Flags for the author :
  1. La clause sous relecture est rendue au mot près. « Un décideur qui lise le contexte, se
     passe d'enquête locale, tienne l'agrégat et batte ce plancher n'existe pas dans nos
     mesures. » Les quatre membres sont dans l'ordre de l'anglais, et « se passe d'enquête
     locale » y rend « needs no local survey », clause portante et non confirmée par l'auteur.
  2. Coupe de phrase déplacée, une seule fois. L'anglais écrit la première limite en une
     phrase, « The tabular references read 39 203 survey trips where the agents read none, so
     no result here compares two decision-makers at equal information. » Le français la coupe
     en deux, la phrase d'un seul tenant dépassant 25 mots (R1). Le sens et l'ordre sont
     conservés, et la seconde phrase porte le connecteur « donc ».
  3. Constat de rendu, sans correction. Le § 7.2 anglais annonce quatre limites « d'une phrase
     chacune » au plan, et en écrit neuf pour quatre limites : la deuxième en porte trois, la
     troisième deux. Le rendu suit l'anglais et n'ajuste rien.
  4. Constat de rendu, sans correction. « Two things stay open » est rendu par « Deux questions
     restent ouvertes », « chose » ayant déjà servi trois phrases plus haut pour « This paper
     establishes four things ».
  5. Les signalements de fond du compte-rendu anglais tiennent sans changement : la clause
     « sans enquête locale » non tranchée, l'ajout de Chopra et al. (2024), la subsistance de
     « dans la conception actuelle », la phrase sur l'avarie moteur reprise du § 6.3, et le
     constat que la section 6 ne porte aucun intervalle.
=== FIN DU COMPTE-RENDU ===
-->
