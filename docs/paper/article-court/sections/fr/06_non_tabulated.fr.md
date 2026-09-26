# 6. Le régime non tabulé : un événement tracé jusqu'à la décision
<!-- Rendu français du brouillon anglais validé, article court AAMAS 2027, PLAN.md § 6.
     Rendu le 2026-09-22 par l'agent article-writer, consigne R17 : l'anglais est la source,
     le français en est le rendu fidèle, à coupes de paragraphes et chiffres identiques.
     Aucun ajout de fond, aucune correction de fond ; les problèmes relevés au rendu vivent
     au compte-rendu. Les commentaires de source sont ceux du fichier anglais, repris mot
     pour mot. Nombres convertis aux usages français : espace fine pour les milliers,
     virgule pour les décimales. -->

L'enquête ménages-déplacements tabule un jour ordinaire, et aucun autre. Cette section suit
un événement qu'aucune variable ne porte, chez un agent, de son entrée en mémoire jusqu'aux
décisions qu'il a changées.

## 6.1 Ce que les 21 variables ne portent pas

Aucune des 21 variables n'enregistre ce que la personne a vécu la veille, ni ce qu'elle a lu
le matin. Un décideur qui ne reçoit que ces entrées ne peut répondre à rien d'autre. Sa
prédiction au lendemain d'un incident est égale à celle de la veille, par identité et non
par mesure.

<!-- source: fr/07_Adaptation.md, chapeau : « Aucune ne porte le vécu de la personne […]
     Un décideur qui ne reçoit que ces 21 entrées ne peut répondre à rien d'autre » ;
     § 7.2.1 pour l'écart nul par identité et l'absence de comparateur jouable. -->

## 6.2 Le mécanisme

Un événement entre dans la mémoire de l'agent à l'un de deux moments. Ce qui est vécu entre
après le déplacement qui l'a produit, et ce qui est lu entre au réveil. L'événement
reçoit à l'entrée une gravité et une valence, subie ou heureuse. La gravité seule fixe la
durée pendant laquelle le souvenir reste servi. Dans l'exécution rapportée ici, la gravité
était déclarée avec l'incident plutôt que notée par le modèle.

<!-- source: fr/07_Adaptation.md § 7.1 : deux prises (après un déplacement, au réveil),
     estimation d'importance et de valence à l'entrée, « cette estimation, et elle seule,
     fixe la gravité de l'entrée » (llm/gravite.py, cinq intensités ; ticket 100, D3 et D4).
     ⚠ Réserve du master portée dans la phrase : « la campagne rapportée est antérieure à la
     décision D4 du ticket 100 : l'agent n'y estime pas encore le choc à l'entrée » (§ 7.2.2),
     la gravité venant de la déclaration du choc (ticket 079 ; 30 puis 20 minutes, soit 0,700
     puis 0,533). -->

Un événement noté fait exactement un saut au-delà de celui qui le porte, par le foyer, le
soir. Le cas d'un agent seul, rapporté ci-dessous, n'exerce pas ce saut.

<!-- source: fr/07_Adaptation.md § 7.1, récit du soir et saut unique (ticket 100, D1 et D2,
     champ de provenance distinguant une croyance entendue d'une croyance vécue).
     Relecture v1, N1 : la description de conception (récit du soir, entrée dans la réflexion
     des auditeurs) vit désormais au § 3.3 (item T2) ; il ne reste ici que l'existence du saut
     et le fait qu'il n'est pas exercé.
     ⚠ Aucun code au 22 septembre : la note de travail du master interdit de passer ce
     passage au passé avant le lot 4 du ticket 100 et une campagne jouée. Écrit ici au
     présent de conception, et borné par la dernière phrase. -->

Un effet s'éteint de deux façons, et la mesure les distingue. Il s'éteint par contradiction
quand l'agent refait le trajet et que rien ne se reproduit, et par usure quand le souvenir
cesse d'être servi.

<!-- source: fr/07_Adaptation.md § 7.1, troisième paragraphe : extinction par contradiction
     ou par usure, « et elles se distinguent à la mesure ». La prédiction stratifiée du
     master (contradiction datée chez ceux qui continuent d'utiliser le mode) n'est pas
     reprise : elle n'est pas mesurée sur le cas tracé. -->

Deux maillons de cette chaîne sont démontrablement une génération de texte. Le premier
écrit la trace de ce qui vient d'arriver, le second entretient la croyance qui s'en tire.
Noter la gravité n'est pas établi comme une génération de texte. Un classifieur à sortie typée pourrait en
principe rendre les deux, sans qu'aucune expérience de cet article ne l'ait testé.

<!-- source: fr/01_Introduction.md l. 81, commentaire de périmètre du ticket 101 § 2 : la
     consolidation — écrire la trace, entretenir la croyance — est une génération de texte
     que le classifieur à sortie typée ne produit pas ; « un classifieur à sortie typée
     pourrait en principe les rendre aussi, et aucune expérience de cet article ne l'a
     testé. Ne pas durcir cette phrase en une impossibilité de principe. » Ordre des deux
     énoncés imposé par le PLAN § 6.2. -->

## 6.3 Le dispositif

Nous jouons un agent deux fois, exposé et témoin, et nous lisons l'écart entre les deux
exécutions. L'incident est une avarie moteur qui impose un retard sur un trajet en voiture,
puis un retard moindre le lendemain. Les deux exécutions gardent la mémoire active. La
voiture reste offerte le lendemain matin, ce qui est la condition pour mesurer un arbitrage
et non une contrainte.

<!-- source: fr/07_Adaptation.md § 7.2.2 : un agent joué deux fois, avarie moteur, 30 puis
     20 minutes de retard, « le véhicule reste offert le lendemain, ce qui est la condition
     pour mesurer un arbitrage plutôt qu'une contrainte, et ce qu'une avarie moteur ne
     produirait pas dans le monde réel » (ticket 079). Relecture v1, § 9 bis : la phrase sur
     l'immobilisation réelle du véhicule est une limite et part au § 7.2 (agent voisin) ; la
     clause « mémoire désactivée sur le banc » est dite une fois au § 3.3 et n'est plus
     répétée ici. -->

Les opinions sont recueillies hors décision, sur six critères déclarés, à quatre jalons. Le
critère d'écologie, qu'aucun incident ne vise, sert de question témoin.

<!-- source: fr/07_Adaptation.md § 7.2.3 : affinites_declarees.csv, échelle de Likert 0-10,
     critères d'Adam & Gaudou (2025), un questionnaire par mode, jalons aux jours 12, 17,
     31 et 40. -->

## 6.4 Résultats

La voiture est offerte aussi souvent qu'avant l'avarie, et cesse pourtant d'être prise.
L'agent exposé la prend neuf fois sur dix avant l'avarie, et trois fois sur dix ensuite.
L'agent témoin tient son taux d'un bout à l'autre.

*Tableau 4 — Voiture retenue quand elle est offerte, agent exposé et agent témoin.*

| Période | Agent exposé | Agent témoin |
|---|---:|---:|
| Avant l'avarie | 94 % (34/36) | 90 % (28/31) |
| Après l'avarie | 32 % (12/38) | 92 % (45/49) |
| Après le retour | 88 % (35/40) | 87 % (40/46) |

<!-- source: fr/07_Adaptation.md § 7.2.3, premier paragraphe : moves.csv des deux exécutions,
     colonne « Modes proposés au LLM », décisions du modèle seules. Fractions du master
     reprises telles quelles, converties en pourcentages par consigne R13. ⚠ Le master ne
     date pas les trois fenêtres : il écrit « avant l'incident », « ensuite », « puis ». Les
     trois libellés de période sont écrits ici, la troisième fenêtre étant rapprochée du
     retour daté du 15 avril. À faire confirmer.
     Relecture v1, N2 : tableau numéroté « Table 4 » par cohérence avec les trois autres. Si
     la compilation (G4) dépasse 8 pages, il redevient une phrase, déjà rédigée : « The car is
     taken on 94 %, 32 % then 88 % of the trips where it is offered, against 90, 92 and 87 %
     for the control agent. » -->

La propension quotidienne à la voiture chute le jour de l'avarie et revient quinze jours
plus tard (figure 5). Elle passe de 90 % la veille à 40 % le jour même, puis oscille
entre 5 et 52 %. Elle rejoint la bande de l'agent témoin, qui ne quitte jamais 65 à 90 %,
le 15 avril.

<!-- source: fr/07_Adaptation.md § 7.2.3 et figure 7.1 : moves.csv, colonne
     P(Voiture Privée) %, moyenne quotidienne des décisions du jour, aucun découpage en
     phases. -->

*Figure 5 — L'effet dure exactement ce que le souvenir dure dans le prompt.*

Des quatre voies par lesquelles le passé atteint une décision, une seule a porté tout
l'effet. Le récit de l'avarie figure dans le bloc « ce qui a changé récemment ». Il y est
présent dans 75 des 376 prompts de décision, du jour de l'avarie au quinzième jour qui suit.
Le rappel par similarité n'a jamais ramené le souvenir, et la croyance que la consolidation
du soir en a tirée n'a atteint aucun prompt. Les quinze jours se déduisent de la gravité,
et non d'un nombre posé à la main.

<!-- source: fr/07_Adaptation.md § 7.2.1 : llm_exchanges.jsonl, 75 prompts sur 376 ;
     trace_rappel.jsonl, aucune occurrence parmi les souvenirs servis ; llm/noyau.py,
     bloc_connaissances et duree_service_jours, 15,29 jours pour une gravité de 0,70, valeur
     écrite avant l'exécution (specs/ticket_095/tests.md) ; sélection par confiance puis
     nombre d'observations, six croyances retenues. Les quatre voies sont celles du § 3.4 des
     masters ; le § 3 de l'article court les nomme. -->

L'effet s'est éteint par usure plutôt que par contradiction. L'agent a repris la voiture
douze fois pendant la période, sans qu'aucune contradiction de croyance soit enregistrée. La
croyance née de l'avarie n'a jamais été servie, si bien que rien ne l'a contredite. Le récit
quitte les prompts de décision après le 13 avril, et la propension rejoint la bande du
témoin le 15 avril. Deux sources indépendantes donnent ces dates, le texte envoyé au modèle
et les probabilités qu'il a rendues.

<!-- source: fr/07_Adaptation.md § 7.2.3, troisième et quatrième paragraphes :
     agent_memory_events.jsonl de l'exécution exposée, zéro contradiction de concept ;
     llm_exchanges.jsonl, dernière occurrence du récit ; moves.csv pour le retour.
     ⚠ Réserve du master, note de travail : le « zéro contradiction » vient du ticket 095 § 1
     (campagne du 077) et reste à recouper sur l'archive 2026-09-21 qui produit les autres
     chiffres. -->

Les opinions déclarées baissent après l'avarie, puis reviennent. Cinq des six critères de la
voiture chutent au jalon qui la suit, la sécurité passant de 8 à 3 sur une échelle de dix.
Les cinq ont retrouvé leur valeur de départ aux deux jalons suivants. Le critère d'écologie
reste à 3 tout du long, et l'agent témoin ne bouge sur aucun des six. Les deux agents
dérivent sur les quatre autres modes sans motif commun, ce qui laisse la voiture comme seul
mode qui les sépare.

<!-- source: fr/07_Adaptation.md § 7.2.3, cinquième et sixième paragraphes : sécurité 8 → 3,
     praticité 9 → 6, confort 8 → 5, rapidité 9 → 8, coût 6 → 5 ; écologie à 3 aux quatre
     jalons ; dix-neuf des trente séries dérivent chez l'exposé, seize chez le témoin. Deux
     critères sur cinq sont cités, faute de place. ⚠ Le master note que la dynamique entre le
     deuxième et le troisième jalon n'est pas observée, et que cet intervalle est celui où le
     récit quitte le contexte. -->

Une seconde expérience porte le même canal jusqu'à une information seulement lue. En cours,
elle sert cinq articles datés de la presse toulousaine contre vingt signes écrits avant tout
appel au modèle (annexe E).

<!-- source: fr/07_Adaptation.md § 7.3 : cinq articles de la presse toulousaine, conditions
     C1 à C3, vingt signes préenregistrés (figure 7.3). Deux phrases et aucun chiffre de
     résultat, par consigne du PLAN § 6.4 ; la campagne exp_05a-e n'a pas tourné. -->

Le chemin tracé ici repose sur un agent et un événement. Nous revendiquons le chemin, non
son amplitude. La section suivante lit ces mesures, avec celles du jour ordinaire, pour ce
qu'elles impliquent sur la place de la délibération.

<!--
=== SECTION REPORT ===
Section        : 06 — Le régime non tabulé : un événement tracé jusqu'à la décision
File           : docs/paper/article-court/sections/06_non_tabulated.fr.md
Words / budget : 822 / 750 (+9,6 %) — anglais source : 791 mots, écart de rendu +3,9 %
Skeleton       :
  L'enquête ménages-déplacements tabule un jour ordinaire, et aucun autre.
  Aucune des 21 variables n'enregistre ce que la personne a vécu la veille, ni ce qu'elle a lu le matin.
  Un événement entre dans la mémoire de l'agent à l'un de deux moments.
  Un événement noté fait exactement un saut au-delà de celui qui le porte, par le foyer, le soir.
  Un effet s'éteint de deux façons, et la mesure les distingue.
  Deux maillons de cette chaîne sont démontrablement une génération de texte.
  Nous jouons un agent deux fois, exposé et témoin, et nous lisons l'écart entre les deux exécutions.
  Les opinions sont recueillies hors décision, sur six critères déclarés, à quatre jalons.
  La voiture est offerte aussi souvent qu'avant l'avarie, et cesse pourtant d'être prise.
  La propension quotidienne à la voiture chute le jour de l'avarie et revient quinze jours plus tard (figure 5).
  Des quatre voies par lesquelles le passé atteint une décision, une seule a porté tout l'effet.
  L'effet s'est éteint par usure plutôt que par contradiction.
  Les opinions déclarées baissent après l'avarie, puis reviennent.
  Une seconde expérience porte le même canal jusqu'à une information seulement lue.
  Le chemin tracé ici repose sur un agent et un événement.
Checker        : verifier_forme.py sort 0, « Aucune consigne mécanique en faute ».
                 Deux constats R1 de la première passe ont été levés par réécriture, et tous
                 deux venaient du découpeur de phrases, qui ne coupe pas devant une majuscule
                 accentuée (« À l'entrée », « Écrire la trace »). Les deux phrases concernées
                 font 14 et 17 mots une fois coupées ; la réécriture ne change aucun sens.
                 Séparateur de milliers : espace simple, convention des masters français
                 vérifiée sur 08_Limitations.md (« 1 000 personas », « 39 203 »).
Terms defined here     : gravité et valence à l'entrée ; extinction par contradiction et par
                 usure ; le couple exposé / témoin ; la question témoin portée par le critère
                 d'écologie.
Terms used, undefined upstream : aucun en français non plus. Les quatre voies du prompt, le
                 bloc « ce qui a changé récemment », le rappel par similarité, la croyance et
                 la consolidation du soir viennent du § 3.3 ; la masse de probabilité et la
                 chaîne de véhicules des §§ 3.2 et 3.4 ; les 21 variables et le banc du § 4.
                 Ces sections n'ont pas encore de rendu français : les termes retenus ici
                 fixeront leur vocabulaire.
Figures cited  : identiques à l'anglais, valeurs et réserves comprises.
                 94 / 32 / 88 % et 90 / 92 / 87 % (tableau 4) — fr/07_Adaptation.md § 7.2.3 —
                 libellés de période écrits au rendu anglais, à confirmer.
                 90 % → 40 %, puis 5 à 52 %, bande du témoin 65 à 90 %, retour le 15 avril
                 (figure 5) — fr/07_Adaptation.md § 7.2.3 et figure 7.1.
                 75 des 376 prompts de décision, quinze jours — llm_exchanges.jsonl et
                 llm/noyau.py, duree_service_jours (15,29 jours pour une gravité de 0,70).
                 Douze reprises de la voiture, zéro contradiction de croyance —
                 agent_memory_events.jsonl — RÉSERVE, voir signalements.
                 Sécurité de 8 à 3 sur une échelle de dix, écologie à 3 aux quatre jalons —
                 fr/07_Adaptation.md § 7.2.3.
                 Cinq articles de presse, vingt signes — fr/07_Adaptation.md § 7.3 — campagne
                 en cours, aucun chiffre de résultat.
Placeholders   : aucun.
Left out       : rien de l'anglais. Le rendu ne retire ni n'ajoute aucune phrase ; les deux
                 seules coupes de phrase déplacées sont dites ci-dessus (R1 mécanique).
Flags for the author :
  1. Terme choisi au rendu, à valider. L'anglais dit « the criterion on the environment » et
     « the environment criterion » ; le master fr/07_Adaptation.md nomme ce critère
     « l'écologie ». Le rendu écrit « le critère d'écologie » aux deux endroits, par la
     consigne « pour tout terme absent de la table, suivre les masters ».
  2. Terme choisi au rendu. « severity » est rendu par « gravité », qui est le mot du master
     (« Cette estimation, et elle seule, fixe la gravité de l'entrée »). « sévérité » n'est
     employé nulle part dans les masters et ne l'est pas ici.
  3. Terme choisi au rendu. « control agent » est rendu par « agent témoin », et « control
     question » par « question témoin ». Le master emploie « agent non exposé » et
     « témoin » ; la consigne de l'auteur fixe « témoin ».
  4. Les signalements de fond du compte-rendu anglais tiennent sans changement et ne sont pas
     répétés ici : la réserve sur le « zéro contradiction » (campagne du 077, à recouper sur
     l'archive 2026-09-21), le tableau 4 qui est un quatrième tableau là où le plan en
     plafonne trois, et les dépendances au § 3.3 pour le récit du soir et la mémoire du banc.
  5. Report de la correction de l'auteur du 2026-09-22. Le § 6.4 disait « revient une
     quinzaine de jours plus tard » dix lignes au-dessus de « Les quinze jours se déduisent de
     la gravité » ; il dit désormais quinze jours aux deux endroits. La durée mesurée est de
     15,29 jours de service du souvenir, pour une avarie le 30 mars et un retour dans la bande
     du témoin le 15 avril. Le résumé porte la même correction.
  6. Constat de rendu, sans correction. La dernière phrase du § 6.2 anglais dit qu'aucune
     expérience n'a testé le classifieur sur la notation de la gravité ; le § 7.1 écrit que
     noter la gravité est la tâche du modèle de langue « dans la conception actuelle ». Les
     deux énoncés se tiennent, et leur voisinage mérite une lecture d'ensemble.
=== FIN DU COMPTE-RENDU ===
-->
