## [2026-07-31] La voiture aussi reste là où on l'a garée

Le vélo avait cessé de se téléporter la veille ; la voiture, elle, était toujours
disponible partout et tout le temps. Il suffisait d'en posséder une pour pouvoir
démarrer depuis n'importe quel point de la ville — y compris un bureau où on était
arrivé en tram. C'était, sur le mode qui pèse le plus lourd dans les parts modales, le
même véhicule fantôme que celui corrigé pour le vélo.

**Le véhicule est désormais un lieu**, vélo et voiture traités à l'identique par trois
règles :

- **On ne conduit que ce qui est là.** Un mode véhiculé n'est proposé que si l'agent
  possède le véhicule *et* qu'il est garé à son point de départ.
- **Le véhicule suit celui qui l'utilise.** Il se déplace avec l'agent qui le prend, et
  reste sur place sinon. Le vélo laissé au bureau n'est plus réputé retrouvé à la maison
  le soir — c'était le dernier vestige de téléportation de la version précédente.
- **On ramène son véhicule chez soi.** Sur un trajet de retour au domicile partant d'un
  lieu où le vélo ou la voiture est garé, les options sont restreintes à ce mode. C'est
  un filtre sur les itinéraires candidats, pas une décision : **aucun appel LLM
  supplémentaire**, et si les deux véhicules sont là, le choix reste au LLM.

Un agent qui part travailler à vélo n'a donc plus de voiture au bureau à midi, et il
rentre à vélo le soir. Les deux véhicules ne peuvent plus être « quelque part » en même
temps.

**Avant :** posséder une voiture suffisait à pouvoir la prendre depuis n'importe où ;
un vélo laissé au travail réapparaissait au domicile en fin de journée.
**Après :** chaque véhicule a une position, qui contraint les modes offerts au départ et
impose le retour en fin de boucle.

**Ce qui reste approximé, et mesuré comme tel.** Une étape intermédiaire contourne le
verrou de retour : domicile → travail en voiture, travail → sport à pied, sport →
domicile en bus laisse la voiture au travail. Ces orphelins sont ramenés au domicile — un
agent privé de sa voiture pour tout le reste de la simulation serait un biais bien pire —
mais comptés, avec une alarme `[ALARME]` si le rattrapage dépasse 5 % des retours au
domicile. Non traité non plus : la voiture est un bien du ménage mais sa position est
suivie par personne, et le park-and-ride reste hors de portée du modèle par trajet.

`vehicle_chain_enabled=false` rétablit l'ancien comportement, pour mesurer l'effet sur
les parts modales à population égale.

---

## [2026-07-31] La calibration tient hors de son jeu d'entraînement (action A4)

Le volet 2 n'avait jusqu'ici qu'un seul type de chiffre : celui mesuré sur le jeu qui a
servi à **optimiser** les prompts. Un composite d'entraînement ne distingue pas un prompt
qui a compris la population d'un prompt qui a mémorisé ses 298 personas — et le store ne
portait strictement aucune évaluation sur le jeu de test. Vérifié avant de payer quoi que
ce soit : zéro éval « test » dans les deux stores, et les trois évals « val » qui
existaient dataient d'un autre modèle, donc inutilisables.

La lignée épinglée est désormais mesurée **entière** — six nœuds sur six, pas seulement
ses extrémités — sur les 106 décisions du jeu de test, sous le régime de production.

**Ce que « généralisation » veut dire ici, et la page le dit en toutes lettres.** La
question n'est pas rhétorique : un découpage par personne soutient « des individus jamais
vus », un découpage par déplacement seulement « d'autres trajets des mêmes individus ».
La réponse est établie sur les fichiers eux-mêmes, pas sur la foi de la règle déclarée :
le découpage est **par personne**, et les 66 personnes du test n'apparaissent dans aucun
des 298 personas du train. C'est bien l'affirmation forte. Au passage, le jeu de
screening est au contraire entièrement inclus dans le train — ce qui lui interdit ce
rôle, et explique qu'on ne l'ait pas utilisé.

**Le résultat, et il aurait été lu à l'envers sans son témoin.** Lu brut, l'écart
ressemble à du surapprentissage : la graine passe de 24,35 à 31,60, la feuille de 22,24 à
24,06. Il n'en est rien. Les divergences par strate sont biaisées vers le haut à petits
effectifs, et le train porte 298 personnes contre 66 pour le test. Le témoin le chiffre
sans un seul appel LLM, en rejouant le score des décisions **déjà stockées** du train sur
200 sous-ensembles de 66 personnes : 29,84 pour la graine, 26,90 pour la feuille. La
seule réduction d'effectif coûte donc +5,49 et +4,66 points — du même ordre que les +5,02
mesurés la veille sur la simulation. À effectif neutralisé, la feuille est **meilleure**
sur le test que sur le train (−2,84), et les six nœuds tombent dans la bande du témoin :
**aucun surapprentissage détectable**.

**Le gain survit ; son amplification n'est pas démontrée, et la page ne la revendique
pas.** Entre la graine et la feuille, la calibration gagne 2,12 points sur le train et
7,54 sur le test. Tentant d'en conclure que le prompt calibré généralise mieux qu'il
n'apprend — sauf qu'un second témoin, apparié celui-là (les deux prompts scorés sur les
*mêmes* personnes tirées, donc bien moins bruyant), place le gain d'entraînement à +2,94
sur une bande allant de −1,84 à +8,24. Les 7,54 y tombent. Ce qui est acquis, c'est que
le gain **n'était pas un artefact du jeu qui a servi à l'obtenir** ; le reste demanderait
plus de 66 personnes.

**Une confusion résiduelle est publiée plutôt que tue.** Le moteur retire délibérément la
section « Historique » — la mémoire du run source, non reproductible — des jeux de
retenue, alors qu'elle couvre 86 % des records du train. Le prompt de test n'est donc pas
seulement adressé à d'autres personnes : il est aussi plus court d'une section. Les deux
effets sont mêlés, rien dans les données ne les sépare, et la page l'écrit.

Ces chiffres ne rejoignent ni la trajectoire, ni la lignée, ni la matrice comparative : le
jeu de retenue est un troisième substrat, et coller une colonne de 66 personnes à côté de
colonnes de 881 rejouerait exactement la confusion corrigée la veille. La matrice y
renvoie, elle ne l'absorbe pas.

**Avant :** le volet 2 ne savait dire que ce que valaient ses prompts sur le jeu qui les
avait produits — aucune manière de distinguer un progrès réel d'une mémorisation.
**Après :** un score hors échantillon, sur des individus jamais vus, accompagné des deux
témoins qui empêchent de le lire de travers et de l'aveu de ce qu'il mêle encore.

Coût : 98 appels LLM pour les six nœuds (~34 pour les seules extrémités). Reprise par
nœud, gratuite depuis le cache.

---

## [2026-07-31] Le gain de la calibration se transporte, son niveau non (action A3)

La matrice « Synthèse comparative » alignait cinq colonnes comme si elles se comparaient. Elles
ne se comparaient pas : la simulation était scorée sur le run épinglé, la calibration sur ses
**personas gelés** — un sous-ensemble d'un run de deux semaines plus tôt. Deux mesures faites
sur deux populations, présentées côte à côte, avec la même échelle de couleurs.

La page l'avoue désormais colonne par colonne, au lieu de le noyer dans un paragraphe de bas de
section : sous la matrice, chaque colonne déclare son substrat et, pour la calibration, le nœud
et le régime de mesure exacts. Le volet 2 gagne aussi un tableau qui met les deux chiffres d'un
même prompt face à face — son composite sur le jeu commun et son composite sur les personas
gelés — parce que ce sont deux nombres différents et que le lecteur doit savoir lequel il lit.
Le bloc « avant / après » historique porte maintenant son substrat dans son titre.

La mesure est faite : `make common-set-eval` a rejoué la graine et la feuille de la lignée
épinglée sur un échantillon **du run**, sous le régime épinglé, avec une couverture de 100 %
(80 personnes sur 80). L'échantillon est gelé et reproductible — tirage par personne, jamais par
trajet, sur un hachage stable de l'identifiant : 509 décisions, 80 personnes. C'est le plus petit
tirage dont toutes les strates de l'enquête atteignent l'effectif minimal ; en dessous, des
tranches d'âge se vident et le score cesse d'être comparable à celui de la simulation. Le
hachage est volontairement dans un espace distinct de celui du découpage train/val/test, sans
quoi l'échantillon n'aurait contenu que des personas ayant servi à optimiser la lignée.

La commande ne redécoupe pas les lots elle-même : elle passe par l'évaluateur du moteur, donc par
les défenses posées la veille contre les réponses amputées de personas. Bien lui en a pris —
**29 lots sur 128 sont revenus incomplets**, jusqu'à 2 personas rendus sur 8, tous rattrapés par
re-tir en moitiés. Une boucle de lotissement réécrite pour l'occasion aurait scoré sur une
sous-population sans que rien ne le signale.

**Le résultat, et il n'est pas flatteur.** Le gain de la calibration **se transporte** : entre la
graine et la feuille, 2,13 points de composite sur le jeu commun contre 2,12 sur les personas
gelés. Le progrès mesuré sur le jeu d'entraînement était donc réel, et pas un artefact de son
propre instrument. Mais le **niveau**, lui, ne se transporte pas du tout : les deux prompts
passent de 24,35 et 22,24 sur les personas gelés à **38,53 et 36,41** sur le jeu commun. Le même
texte, mesuré par le même modèle sous la même politique, est ~14 points moins fidèle dès qu'on
change de population.

**Une partie de cet écart n'a rien à voir avec les prompts, et la page le chiffre au lieu de le
supposer.** Les divergences par strate sont biaisées vers le haut quand les effectifs sont
petits : mesurer sur 81 personnes n'est pas mesurer sur 881. Une nouvelle colonne, « Sim.
(éch. V2) », restreint la simulation **aux mêmes 81 personnes** — sans un seul appel LLM — et
montre que la simulation passe alors de 24,37 à 29,39. Soit **+5,02 points pour la seule
réduction d'effectif**, à décisions inchangées. C'est à cette colonne que la calibration doit
être comparée, et non à celle du run entier. Elle reste au-dessus : sur le même substrat et à
effectif égal, le volet 2 est moins fidèle à l'enquête que la simulation.

**Ce que le quota a appris.** Le seau journalier du free tier Google ne se réinitialise pas à
minuit UTC mais à **minuit Pacific**. Plus retors : une sonde de quatre appels a réussi sur une
clé pourtant épuisée avant que le compteur ne rattrape — l'application du quota journalier n'est
pas exacte à la frontière, et aucun petit test ne dit de façon fiable si un seau est ouvert. La
mesure a finalement coûté 175 appels sur la seconde clé.

**Avant :** cinq colonnes d'apparence homogène, dont deux portaient en réalité sur une autre
population, et un avertissement générique en fin de section.
**Après :** sept colonnes, chacune annonçant sa population, son effectif et son régime de
mesure — dont un témoin de taille qui rend l'écart du volet 2 lisible au lieu de le laisser
attribuer au prompt.

---

## [2026-07-31] Le volet « modèle statistique » entre enfin dans la comparaison (action A8)

La matrice de la page de synthèse portait une colonne « Modèle » entièrement vide. Le modèle
existait pourtant, entraîné et sérialisé la veille — mais il n'avait jamais rencontré une seule
décision du run qui sert de jeu commun. Il la remplit désormais, et il faut lire ce chiffre en
sachant ce qu'il est.

**Ce qui a été mesuré.** La politique statistique est appliquée aux 5 945 décisions du run
épinglé — exactement le périmètre du volet 1, construit par le même code et les mêmes
exclusions, sinon les colonnes ne se compareraient pas davantage qu'avant. Pour chaque
déplacement, les 21 variables du contrat sont reconstruites depuis le persona, la chaîne
d'activités et la géographie, puis le modèle prédit une distribution sur quatre modes.

**La correction qui change tout : l'offre réellement proposée.** Le modèle prédit sur quatre
modes sans savoir lesquels étaient disponibles ; la simulation, elle, ne choisit que parmi les
itinéraires calculés pour ce trajet-là. Sans correction, on reprocherait au LLM de n'avoir pas
choisi un mode qu'on ne lui a jamais offert. Chaque prédiction est donc restreinte aux modes
proposés, puis ramenée à 100 %. L'effet n'est pas décoratif : 3,4 % de la masse prédite tombait
en moyenne sur des modes indisponibles, la correction déplace le mode le plus probable sur 142
décisions, et rapproche les parts modales de l'enquête de 17,9 à 14,1 points d'écart cumulé.

**Deux lectures, et il faut les deux.** Comme pour la simulation, la page rapporte la masse de
probabilité et le mode effectivement retenu. L'écart entre les deux est structurel : le modèle
calibre bien le vélo en masse mais ne l'élit presque jamais. N'afficher que la première le
flatterait, n'afficher que la seconde le condamnerait.

**Le modèle écrase les deux autres volets, et c'est attendu.** Il est entraîné sur l'enquête qui
sert ici de cible : sa victoire ne dit rien de la qualité relative du LLM, elle borne ce qu'un
modèle purement statistique atteint sur ce jeu. L'avertissement est désormais posé juste
au-dessus de la matrice, là où le lecteur voit le chiffre, et non trois sections plus loin.

**Deux surprises, rapportées telles quelles.** Aucune décision n'a dû être écartée : on
attendait environ 5 % de trajets hors du périmètre d'enquête, la population de ce run tombe
intégralement dedans — les 5 % avaient été mesurés sur un autre tirage de population. Et 15,5 %
des décisions n'ont pas de catégorie socioprofessionnelle : la population simulée utilise un
libellé « Retired » que le recodage de l'enquête ne produit jamais. Il est laissé manquant
plutôt que rapproché à l'aveugle d'une catégorie voisine — l'occupation principale, elle, porte
bien « Retraité ».

**Avant :** colonne « Modèle » entièrement « n. d. » ; rien dans la page ne situait le modèle
face à la simulation ou à la calibration.
**Après :** deux colonnes remplies sur les sept dimensions, mesurées sur le même run et avec la
même loss que les autres, assorties du cadrage qui empêche de les surinterpréter.

---

## [2026-07-31] Le modèle oubliait des personas, et personne ne le voyait (action A10)

Depuis la bascule vers les comptages pondérés, ré-évaluer une lignée de prompts « n'avançait
plus ». Aucune erreur, aucun message : la commande tournait et rien ne progressait. La cause
supposée — une sortie cinq fois plus longue qui dépasserait le délai d'attente de 240 s de
l'appel Gemini — était fausse. Les mesures l'ont écartée en trois appels.

Ce que l'instrumentation a montré, sur des lots réels : **3,6 à 8,8 secondes** par appel pour
une limite de 240 s, **`finishReason=STOP`** partout, **2 742 tokens** de complétion au pire
pour un plafond de 4 096. Ni lenteur, ni troncature. Le vrai défaut est ailleurs et bien plus
gênant : à 15 personas par requête, **le modèle rend un JSON valide, conforme, complet de son
point de vue — mais qui ne contient que 5 à 8 des 15 personas demandés.** Quatre lots sur
douze étaient ainsi amputés, soit 18 % de la population perdue en silence.

Aucune défense existante ne pouvait le voir : ce n'est ni une erreur réseau, ni une réponse
tronquée, ni un JSON hors-schéma. Le lot passait pour un succès, le score était calculé sur
la population restante, et **mis en cache comme s'il était complet**. Une mesure fausse, donc,
plutôt qu'une mesure absente — le pire des deux.

Trois défenses ont été posées :

- **on compare désormais ce qui a été demandé à ce qui a été reçu**, persona par persona, à
  chaque requête ;
- **un lot incomplet est re-tiré par moitiés.** Redemander la même chose à un modèle réglé en
  décodage déterministe redonne la même réponse : il faut réduire la demande, pas insister. Un
  lot revenu à 5 personas sur 15 est ainsi complété à 15 sur 15 en trois appels ;
- **une évaluation dont la couverture reste insuffisante est refusée**, pas stockée. La base ne
  garde pas le nombre de personas réellement vus : un score calculé sur 60 % du jeu y serait
  indiscernable d'un score complet et fausserait toute la trajectoire. Un nœud déclaré
  « manquant » dit la vérité ; un score partiel, non.

L'échec silencieux proprement dit est refermé au passage : la boucle de nouvelles tentatives
rendait une liste vide quand elle s'épuisait, que l'appelant prenait pour un lot légitimement
sans décision. Elle lève maintenant, avec une alarme. Et les trois grandeurs qui ont permis le
diagnostic — tokens produits, raison d'arrêt, latence — sont tracées à chaque appel Gemini et
rappelées dans le texte de chaque erreur, pour que la prochaine panne de ce genre se lise au
lieu de se deviner. Une série de réponses tronquées lève désormais une alarme explicite, une
seule par épisode.

**Avant :** la lignée de prompts n'était lisible que sous `mistral-small-latest` et l'ancienne
politique « mode élu » — ni le modèle de production, ni la politique courante. La page de
synthèse le signalait par un avertissement, et la campagne de calibration ne pouvait pas
reprendre.
**Après :** les six nœuds de la lignée sont mesurés sous le régime épinglé —
`gemini-3.1-flash-lite-preview` et la politique « masse de probabilité », c'est-à-dire le
modèle et la politique de la production. L'avertissement de repli a disparu de la page, qui
affiche désormais la lignée sous **deux** instruments en regard.

Et cette double lecture dit quelque chose : **les deux régimes voient la lignée s'améliorer.**
Sous l'ancien (mistral, mode élu), la calibration gagnait 7,60 points, soit 24,9 % du niveau
de la graine ; sous le nouveau, 2,12 points, soit 8,7 %. Près de trois fois moins en part,
mais **dans le même sens**. Le progrès n'était donc pas un artefact de l'instrument qui avait
servi à l'optimiser — ce qu'on ne pouvait pas exclure jusqu'ici. Son *ampleur*, en revanche,
ne se transporte pas : le chiffre à retenir est celui du régime de production.

---

## [2026-07-31] La référence statistique existe enfin (action A6)

La page de synthèse compare trois façons de décider d'un mode de transport. La troisième —
un modèle statistique entraîné sur l'enquête EMC² 2023 — n'était jusqu'ici qu'une
intention : le jeu de données et le contrat de variables existaient, le modèle non. Il
existe maintenant, il se rejoue en une commande (`make policy`), et il est reproductible à
l'octet près.

Ce que ce volet apporte, ce n'est pas un concurrent loyal : entraîné sur l'enquête qui sert
aussi de cible, il est proche de l'oracle sur les parts modales, et c'est exactement son
intérêt — il **borne** ce qu'un modèle purement statistique atteint, et situe les deux
autres volets par rapport à cette borne. Sur son propre jeu de test (étanche au ménage,
pondéré par les coefficients de redressement de l'enquête) : log-loss 0,5363, 79,5 %
d'accuracy, et 2,1 points d'écart cumulé sur les parts modales — vélo, voiture, transports
collectifs et marche tombent tous à moins de 1,1 point de l'observé.

Trois pièges pouvaient produire un modèle spectaculaire et faux, tous refermés par une
vérification explicite plutôt que par une intention :

- **la distance déclarée trahit le mode.** Pour la marche, elle est une fonction affine de
  la durée : l'utiliser, c'est donner la réponse. Les trois variables concernées sont
  marquées « diagnostic » dans le contrat, et l'entraînement refuse de démarrer si l'une
  d'elles entre dans le modèle ;
- **le découpage train/test doit rester étanche au ménage** — les déplacements d'un même
  foyer partagent son équipement automobile. Il est lu tel quel dans le jeu de données,
  jamais retiré au hasard, et l'arrêt de l'entraînement se règle sur une part détourée
  dans l'apprentissage, jamais sur le test ;
- **les parts modales n'ont de sens que redressées.** La pondération de l'enquête pèse
  l'entraînement et toutes les métriques rapportées.

Le modèle est livré comme un artefact autoportant : il embarque l'ordre de ses variables,
l'encodage de chaque modalité, l'ordre de ses classes, la version du contrat et ses propres
métriques. Qui veut l'utiliser n'a rien à relire des micro-données d'enquête, ni rien à
deviner.

**Avant :** le volet 3 de la page de synthèse affichait « aucun modèle entraîné », et ses
sept dimensions étaient vides.
**Après :** la page montre le modèle, ses métriques de test et ses parts modales prédites
face aux observées. Les sept dimensions **restent vides** : le modèle n'a encore été
appliqué à aucune décision du jeu commun d'évaluation, et c'est l'action A8 qui produira
ces prédictions. La comparaison des trois volets attend donc toujours.

---

## [2026-07-30] Un seul centre-ville pour toute la chaîne (action A9)

Le projet portait deux centres de Toulouse distants de 820 m : celui que l'enquête EMC²
publie dans le contrat de variables (centroïde des zones du secteur Capitole) et un second
codé en dur dans le journal des déplacements. C'est ce dernier qui décidait si un agent
habitait « Toulouse » ou en « 1re couronne ». Résultat : les agents de la bande
intermédiaire changeaient de couronne selon qu'on les regardait par le journal ou par les
variables du modèle statistique, et les deux lectures du lieu de résidence ne se
comparaient plus.

Le centre n'est plus déclaré nulle part au runtime : il est **lu** dans
`feature_spec.json`, par le même point de lecture qui sert déjà au résolveur de zone fine
à refuser une couche dont le centre diverge du modèle. Une définition, un seul endroit qui
la lit — la divergence ne peut plus revenir par recopie.

Le fichier de spécification vient des micro-données PROGEDO, d'accès restreint : sur un
poste qui ne les a pas, il est simplement absent. Ce cas est prévu et tracé dans les logs,
et le repli est la valeur publiée du spec recopiée en constante, jamais l'ancien centre
abandonné. Un test échoue si le repli et le spec se mettent à diverger.

**Avant :** les couronnes de résidence du journal étaient mesurées depuis 43.6047 / 1.4442,
les distances au centre du modèle depuis 43.597347 / 1.444997.
**Après :** les deux depuis 43.597347 / 1.444997, la valeur calculée sur les données de
l'enquête.

⚠ **Les runs déjà archivés ne bougent pas.** La couronne est calculée au moment où le
déplacement est journalisé, puis écrite dans `moves.csv` ; la page de synthèse relit cette
colonne, elle ne la recalcule pas. Le volet 1 affiche donc exactement les mêmes chiffres
qu'avant sur le run épinglé. Seuls les runs postérieurs à ce changement porteront les
couronnes du centre unifié.

---

## [2026-07-30] Le point sait dans quelle zone il tombe (action A7)

Le modèle statistique de choix modal s'appuie sur quatre variables géographiques qui
pèsent lourd dans ses décisions — distance origine-destination, densités, distances au
centre. Toutes supposent de savoir dans **quelle zone fine** de l'enquête EMC² tombe un
point. L'enquête le donne ; la simulation, elle, n'a que des coordonnées. Cette
information manquait : le volet « modèle » de la page de synthèse ne pouvait pas être
calculé, faute de pouvoir reconstituer ses propres variables d'entrée.

Le rattachement existe maintenant, et il rejoue **la formule d'entraînement**, pas une
approximation raisonnable. Deux pièges étaient sur le chemin :

- **La distance.** En simulation on connaît les coordonnées exactes, donc la tentation est
  de mesurer la distance à vol d'oiseau. Ce serait faux : à l'entraînement la distance est
  mesurée entre **centroïdes de zones**, avec une valeur imputée pour les trajets qui
  restent dans une seule zone. Mesuré sur la population : 1,29 km contre 0,65 km sur ces
  trajets-là, soit un facteur 2 — et ce sont exactement les trajets courts où marche, vélo
  et voiture se disputent la décision.
- **Le centre-ville.** Le projet en portait deux définitions distantes de 820 m. Le
  résolveur n'en redéclare aucune : il lit la distance au centre déjà calculée avec le
  centre publié, et refuse de démarrer si la couche et le modèle n'en décrivent pas le
  même (l'action A9 reste ouverte côté `move_logger.py`).

Hors du périmètre d'enquête, rien n'est deviné. Les points concernés sont à 22,8 km en
médiane de la zone la plus proche : ce sont des communes franchement extérieures, pas des
cas limites. Le résolveur renvoie « pas de zone » et laisse l'appelant basculer sur sa
politique de repli. Une alarme se déclenche si le taux hors couche s'envole au-delà de
15 %, signe que la population ou la couche a changé de périmètre.

**Avant :** les six variables géographiques du modèle n'étaient calculables qu'à
l'entraînement ; en simulation, aucune.
**Après :** calculables sur **95,1 %** des paires origine-destination de la population de
référence (95,5 % des localisations), à l'identique de l'entraînement.

⚠ **Ce que cela ne fait pas.** Rien ne prédit encore : le modèle lui-même reste à
entraîner (A6) et à appliquer au jeu commun (A8), et rien n'est branché sur la simulation.
A7 lève le préalable, elle ne produit aucun chiffre de choix modal.

Une nuance à garder en tête pour la suite : 81 des 785 zones n'ont aucun ménage enquêté,
donc pas de densité. Elles concernent 5,5 % des paires exploitables. La valeur est laissée
**manquante**, jamais remplacée par zéro — « aucun ménage enquêté » et « zone déserte » ne
sont pas la même information, et le modèle sait traiter une valeur absente.

---

## [2026-07-30] Le vélo ne se téléporte plus : cohérence de chaîne

Un agent parti travailler en bus retrouvait son vélo pour repartir du bureau. Le vélo
n'était filtré que sur la **possession** (`personal_bike`), jamais sur sa présence
effective là où l'agent se trouve. Résultat : un vélo fantôme, disponible à chaque étape
de la journée quel que soit le mode des trajets précédents.

Le vélo est désormais proposé si l'agent en possède un **et** l'a avec lui : il le suit
quand le trajet est fait à vélo, il est retrouvé au retour au domicile, il reste au point
de départ sinon. Un agent qui n'a pas bougé (même localisation) garde son vélo.

**Avant :** vélo proposé sur 3191 des 5956 trajets d'un run de référence, dont 352 avec un
vélo laissé ailleurs → 18,2 % de part modale vélo (cible enquête EMC² 2023 : 4 %).
**Après :** ces 352 trajets ne peuvent plus être faits à vélo, soit **−5,9 points** de part
modale (18,2 % → 12,3 % en borne haute). Une partie du report devrait aller à la marche,
sous-représentée à 7,7 % contre 26,8 % attendus — l'écart se corrige donc des deux côtés.

Ce qui n'est **pas** traité, et reste à faire pour combler l'écart restant : le vélo est
encore proposé sans plancher d'âge (45 % des moins de 11 ans « possèdent » un vélo, 18,2 %
de leurs trajets se font à vélo) et jusqu'à 30 km à vol d'oiseau. Version simple assumée
côté chaîne : un vélo laissé au travail est réputé retrouvé au domicile le soir.

---

## [2026-07-30] Une trajectoire de calibration lisible bout à bout (action A5, entamée)

⚠ **A5 n'est pas terminée.** Ce qui suit outille la lecture d'une lignée sous un régime
unique et l'affiche ; le **rejeu** que l'action demande n'a produit **aucune évaluation**
(voir « ce qui reste bloqué » plus bas). La page marque donc l'action « partiellement
faite », garde son coût et continue de la compter en attente — un nouvel état, introduit
justement parce que livrer le code d'une mesure n'est pas produire la mesure.

La page de synthèse traçait la calibration en facettant par **modèle d'évaluation**, et
prévenait qu'on ne devait pas lire ces courbes bout à bout. C'était insuffisant sur deux
points, et la page le dit maintenant autrement.

**Un modèle ne suffit pas à définir un régime de mesure.** Le moteur a basculé du « mode
élu par persona » à la masse de probabilité : sous cette politique, les décisions
elles-mêmes changent, donc aucun recalcul de loss ne réconcilie deux évals qui ne la
partagent pas. La page regroupe désormais par **modèle · politique** — deux clés d'API sur
le même modèle restant, elles, une seule courbe. La plage de composite d'un store porte sur
son seul régime de référence, au lieu de mélanger les instruments dans un même intervalle.

**Une courbe chronologique ne dit pas qu'une calibration a progressé.** Elle mêle des
branches et des nœuds sans parenté. La page affiche donc en plus une **lignée** — la chaîne
des mutations acceptées, de la graine à la feuille, épinglée dans `sources.yaml` comme l'est
le run du jeu commun. Sur les 6 nœuds de la lignée retenue, le composite descend de 30,52 à
22,92, soit **−24,9 % d'écart à l'enquête EMC²**, sans changement d'instrument en cours de
route. C'est la seule trajectoire de la page qui se lise comme l'effet du prompt.

Ces 6 nœuds étaient **déjà** mesurés sous un régime unique, dans le store, depuis juillet :
il n'a fallu aucun appel LLM pour le voir — seulement cesser de confondre « modèle » et
« régime », et savoir reconstruire la chaîne. Le régime en question est cependant
`mistral-small-latest` et l'ancienne politique « mode élu » : ni le modèle épinglé, ni la
politique courante. C'est là que l'action reste ouverte.

Reconstruire cette chaîne demandait un détour : les prompts étant adressés par contenu, un
texte déjà produit sur une autre branche est réutilisé avec le parent de sa *première*
création — souvent aucun. Chaîner par le seul champ `parent` s'arrêtait donc au deuxième
nœud et **perdait la graine**, c'est-à-dire la référence à laquelle toute la trajectoire se
compare. La lignée est maintenant reconstruite par les arêtes de mutation.

Nouvelle commande `calibrate reeval` pour rejouer une lignée sous un régime unique : elle
annonce son coût en appels avant de le payer (`--dry-run`), ne paie que les nœuds manquants,
et reprend où elle s'est arrêtée après un épuisement de quota.

**Ce qui reste bloqué (action A10).** Porter cette lignée sur le modèle d'évaluation
*épinglé* n'a pas abouti : sous la politique pondérée, aucune éval ne termine. Les lots
dépassent le timeout de 240 s de l'adaptateur Google et sont retentés cinq fois sans qu'une
seule erreur ne remonte au journal. Réduire les lots de 15 à 8 personas n'a pas suffi. Le
blocage ne concerne pas que cette mesure : **aucune campagne n'a encore tourné sous cette
politique**, donc la prochaine reprise rencontrera le même mur.

**Avant :** les courbes de calibration étaient facettées par modèle, avec l'avertissement de
ne pas les lire bout à bout — et aucune trajectoire ne pouvait l'être
**Après :** une lignée de 6 prompts se lit d'un bout à l'autre sous un régime unique, et le
mélange des régimes est nommé pour ce qu'il est — mais sous un modèle qui n'est pas celui de
la production, et l'action reste comptée en attente

---

## [2026-07-30] Le jeu commun de la page de synthèse est épinglé (action A1)

La page de synthèse lisait son run de référence à travers `experiments/current`, un symlink
qui bouge à chaque simulation. Deux régénérations pouvaient donc décrire deux substrats
différents — mêmes titres, mêmes tuiles, chiffres incomparables — sans que rien ne l'indique.
Le manifeste épingle désormais un chemin d'archive explicite
(`experiments/archive/2026-07-29_18_34`). La tuile « Run » affiche l'état de l'épinglage et
avertit si le chemin configuré se résout ailleurs.

Épingler ne change aucun chiffre : la comparaison des deux `data.json` ne montre que la
nouvelle information d'épinglage et l'horodatage. C'est bien le but — le run décrit était le
bon, il n'était simplement pas garanti de le rester.

Évaluer un autre run reste immédiat, sans toucher au manifeste :
`make synthesis RUN=experiments/archive/<run>`.

La liste d'actions en bas de page conserve maintenant ce qui a été fait : A1 y apparaît barrée
et marquée « faite », avec ce que sa réalisation a produit, et le titre compte les huit actions
restantes. Les identifiants ne sont jamais recyclés — les avertissements de la page et les
tickets y renvoient par numéro. La version précédente de la page est archivée sous
`docs/synthesis/archive/2026-07-30_1037/`.

**Avant :** la page suivait le dernier run en date ; régénérer après une simulation changeait
silencieusement le jeu d'évaluation
**Après :** le run est nommé dans le manifeste et vérifiable par empreinte ; changer de jeu
commun est un acte explicite

---

## [2026-07-30] Page de synthèse : les trois approches face à l'enquête EMC²

Une page HTML autonome (`make synthesis`) rassemble pour la première fois au même endroit
la fidélité des parts modales simulées à l'enquête CEREMA — globalement **et** dans chaque
sous-catégorie : âge, genre, occupation, motif, distance, lieu de résidence. Elle compare
trois approches : la simulation actuelle (le LLM donne des probabilités, la simulation tire
au sort), la calibration de prompt, et le modèle statistique PROGEDO.

Le point qui rend la comparaison possible : les trois volets sont ramenés à une même trame
de décision, puis scorés par **la loss du moteur de calibration elle-même**, importée et non
réécrite. Seule la pénalité de longueur de prompt est neutralisée — elle n'a pas de sens pour
un volet sans prompt. Le substrat commun est un run de simulation, seul terrain qui porte à
la fois les personas complets, les jeux de choix OTP et les coordonnées dont le modèle
statistique a besoin.

Deux constats sortent immédiatement des chiffres. La simulation **sous-estime massivement la
marche** (7,5 % contre 26,8 % attendus) et surestime le vélo (18,8 % contre 4,1 %) : 47 points
d'écart L1 cumulé, le plus gros gisement d'amélioration identifié à ce jour. Et le recalcul de
l'historique de calibration montre que l'écart spectaculaire entre les scores archivés
(~176 contre ~42) n'était **pas** un progrès : c'étaient deux loss différentes. Ramenés à la
même mesure, les deux régimes se recouvrent.

La page ne masque pas ce qui manque : chaque donnée absente devient une carte « Données
manquantes » portant le chemin attendu et l'action qui la produirait. Le volet PROGEDO est
aujourd'hui entièrement dans ce cas, et neuf actions chiffrées sont listées en bas de page.

**Avant :** la fidélité à l'enquête se reconstituait à la main, notebook par notebook, sans
score commun entre la simulation et la calibration
**Après :** `make synthesis` produit la page complète et son JSON en quelques secondes, avec
les sources tracées (chemin, date, empreinte)

---

## [2026-07-30] La calibration mesure à nouveau le prompt de production

La calibration évalue les prompts sur des jeux gelés, extraits de vrais runs — donc rendus
avec les étapes d'itinéraire en puces de même niveau que les options (cf. l'entrée
suivante). Les 803 personas des jeux `v1` sont **tous** concernés : la mesure exposait donc
le modèle juge à la même renumérotation, et une part des personas était comptée avec une
répartition uniforme qu'aucun prompt n'avait produite. Autrement dit : du bruit qui
pénalisait indifféremment toutes les variantes, et pouvait faire accepter une mutation
neutre.

Le traitement des options de la production est désormais appliqué à la mesure : étapes
ré-indentées en sous-puces au moment de construire le lot (le jeu sur disque n'est pas
touché, rien à re-geler) et probabilités hors bornes réalignées sur leur mode. Le drapeau
`prod_option_handling` (défaut : activé) pilote les deux et entre dans la clé de cache
d'éval : les deux régimes ne se mélangent jamais dans le store, et `false` restaure
l'ancien comportement pour reprendre une campagne sur ses évals déjà payées.

**Avant :** une part des personas notée « au hasard » par construction, mêmes prompts,
scores bruités
**Après :** la mesure porte sur le prompt réellement servi en simulation

Bonne nouvelle de calendrier : aucune éval n'avait encore été payée sous le régime de
comptage pondéré actuel — le changement de clé ne coûte donc pas un seul appel LLM.

---

## [2026-07-30] Les étapes d'un itinéraire ne sont plus lues comme des options

Dans le prompt d'itinéraire, chaque option était suivie du détail de ses étapes (« Marche
jusqu'à… », « Bus '401' vers… ») en puces de **même niveau** que la ligne d'option. Plusieurs
modèles (mistral, llama 3.1, gemma) comptaient donc ces étapes comme des options
supplémentaires et renumérotaient tout le bloc : 36 « options » là où 6 étaient proposées.
Leurs probabilités partaient sur des index inexistants, silencieusement écartés — et quand
tout le vecteur y passait, la décision du modèle était remplacée par un tirage **uniforme**
entre les 6 itinéraires. Une voiture choisie à 100 % devenait « un mode au hasard ».

Les étapes sont désormais des sous-puces indentées « · », l'en-tête annonce le nombre
d'options et la plage d'index, et la consigne précise que seules les lignes `- [n]` sont des
options — et que les index repartent de 0 pour chaque persona du lot. En second rideau, une
entrée dont l'index est hors bornes est replacée sur l'option que **son libellé de mode**
désigne au lieu d'être jetée ; si plusieurs options partagent ce mode, la masse est répartie
entre elles (la part modale, qui est la mesure, reste exacte). Ce qui n'est pas rattrapable
sort maintenant en `make error` sous `[ALARME]` au lieu de se fondre dans les warnings.

**Avant :** 12 agents sur 36 touchés décidaient à l'uniforme ; part modale mesurée à 0,41
d'écart de la décision réelle du modèle
**Après :** 1 seul repli uniforme, écart ramené à 0,02 — rejoué sur le run du 2026-07-29

Effet secondaire utile : moins de bruit dans les logs. Les entrées hors bornes à probabilité
nulle — l'essentiel des 299 warnings du run de 5 h 40 du 2026-07-29 — passent en `DEBUG` ;
ne restent visibles que les pertes de masse réelles.

---

## [2026-07-29] `make run` retrouve le modèle GAMA après le déplacement du dépôt

Le dépôt a été déplacé sous `~/Documents/Projects/`, mais deux endroits pointaient encore
sur l'ancien emplacement : le `Makefile` et le workspace GAMA lui-même. Résultat, `make run`
lançait GAMA sur un dossier inexistant — l'IHM s'ouvrait sur un projet mort, et le lancement
finissait en exception SWT.

Le chemin en dur du `Makefile` est remplacé par une racine déduite de l'emplacement du
`Makefile` : déplacer à nouveau le dépôt ne cassera plus rien. Le lien du projet
`CityTransport` enregistré dans `~/Gama_Workspace` a été repointé sur le bon dossier.

**Avant :** `make run` ouvrait GAMA sur un workspace inexistant, exception au démarrage
**Après :** le modèle `City.gaml` se charge, plus aucune erreur au lancement

---

## [2026-07-29] Un jeu d'entraînement sain pour le choix modal — la distance ne trahit plus le mode

Première brique d'une politique de choix modal statistique, destinée à servir de bras de
comparaison face à l'agent LLM (les agents non-LLM se contentent aujourd'hui de prendre la
première option proposée). Le jeu d'entraînement est construit depuis l'enquête EMC²
Toulouse 2023, mais **sans la variable de distance de l'enquête**.

Cette distance était contaminée : pour la marche, elle n'est pas mesurée mais recalculée
depuis la durée déclarée du trajet (58 m/min, exactement). Un modèle entraîné dessus
devinait donc le mode en connaissant déjà la réponse. Elle est remplacée par une distance
entre zones, indépendante du mode, et calculable aussi bien dans l'enquête qu'en cours de
simulation — là où, au moment du choix, il n'existe pas encore de « distance du trajet »
mais plusieurs itinéraires candidats ayant chacun la sienne.

**Avant :** prédiction quasi parfaite de la marche (PR-AUC 0.985) — signature d'une fuite
**Après :** 0.804 sur une distance honnête, et un modèle utilisable en simulation

Le jeu est pondéré par les coefficients de redressement de l'enquête, découpé par ménage
(et non par déplacement, qui laisserait fuir un individu des deux côtés), et accompagné
d'un contrat de features versionné : chaque variable retenue doit être calculable à
l'instant de la décision en simulation, sinon elle est exclue quel que soit son pouvoir
prédictif. Sur ce jeu, les parts modales prédites s'écartent de 3,3 points cumulés des
parts observées, sans aucune repondération artificielle des classes.

Domaine de validité déclaré : l'enquête ne couvre que les **jours ouvrés** et le seul
périmètre où les deux zones du déplacement sont enquêtées.

---

## [2026-07-29] La calibration mesure la valeur des blocs par simple omission

Savoir quel bloc du prompt porte le score se paie en évaluations. La campagne le faisait
par **valeurs de Shapley** : des centaines de coalitions de blocs par passe, recalculées
après chaque acceptation — le poste de dépense le plus lourd du quota journalier, pour un
chiffre dont on n'utilise en pratique que le **classement**. Le réglage
`attribution_method` revient au calcul simple : retirer chaque bloc à tour de rôle et
mesurer ce qu'on perd. Shapley reste disponible en option, pour les moments où la
répartition exacte du gain compte (blocs redondants ou synergiques).

**Avant :** une passe d'attribution ≈ 2 + 25 × 11 = **277 coalitions** à évaluer
**Après :** 1 + 11 = **12 coalitions** — soit ~23× moins, à budget de quota constant

Aucune évaluation déjà payée n'est perdue : les deux méthodes partagent le même cache
adressé par contenu, et les coalitions « prompt complet moins un bloc » leur sont
communes. Repasser à `attribution_method: shapley` réutilise donc tout ce qui a été
mesuré entre-temps.

---

## [2026-07-29] La calibration ne mesure plus le hasard

Le score d'un prompt se calculait en tirant au sort une décision par persona, puis en
comptant les résultats. Sur ~800 personas, ce tirage dispersait chaque part modale
d'environ **±1,7 point** — assez pour noyer une amélioration réelle du prompt, ou pour
faire accepter par chance une mutation sans effet, qui orientait ensuite toute la
campagne.

Le modèle annonçant désormais « voiture 60 %, bus 40 % », il n'y a plus rien à tirer :
on compte directement 0,6 voiture et 0,4 bus. Le score devient **exactement** la
prédiction du prompt, sans le moindre aléa. Deux évaluations du même prompt donnent le
même chiffre.

**Avant :** relancer une évaluation changeait le score de ±1,7 point par mode
**Après :** score identique au chiffre près — un écart de 1 point est un vrai écart

Le tirage au sort reste évidemment en place là où il a un sens : dans la simulation, où
il fait qu'un habitant ne prend pas sa voiture 180 jours d'affilée. Utile pour simuler
un individu, nuisible pour mesurer une population.

Deux conséquences pratiques : `eval_samples` (le nombre de tirages destinés à lisser ce
bruit) **n'a plus d'objet** et n'entre plus dans la clé de cache ; et les effectifs de
strate comptent désormais des **personnes**, non des lignes — les seuils d'exclusion des
petites strates sont donc mécaniquement plus exigeants. L'historique d'évaluations reste
relisible : une décision d'avant la bascule vaut un poids de 1.

---

## [2026-07-29] Détecter le jour où le modèle confond ses options

Le LLM recopie, à côté de chaque probabilité, le mode de l'option concernée. Cette
redondance est maintenant vérifiée : si le modèle annonce « 80 % — la voiture » sur une
option qui est en réalité un bus, ce n'est pas une faute d'étiquette, c'est le signe
qu'il a mélangé les options — et que **tous** ses pourcentages sont attribués aux
mauvaises lignes. Une simulation entière pouvait tourner sur des résultats faux sans que
rien ne l'indique.

Le taux d'incohérence est exposé dans Grafana (attendu : 0 %) et déclenche une alarme
au-delà de 5 % sur 200 options observées. Côté calibration, le mode de chaque option est
désormais lu dans le jeu d'évaluation lui-même plutôt que dans la réponse du modèle : la
mesure ne dépend plus de ce qu'il déclare.

Le dashboard mobilité gagne une section « répartition attendue vs tirée » : ce que le
modèle voulait, ce que les agents ont fait, et l'écart entre les deux.

---

## [2026-07-29] La calibration ne s'arrête plus faute de quota au bout de 27 itérations

Après chaque amélioration retenue, la boucle de calibration recalculait la contribution
de **chaque** bloc du prompt par valeur de Shapley — une attribution exacte, mais qui
consommait à elle seule le quota journalier : la campagne 7 s'est arrêtée après 27
itérations sur 200 prévues.

L'attribution se fait désormais par **omission** (retrait bloc à bloc, `N+1` évaluations
au lieu de ~25 fois plus). C'est moins exact — deux blocs redondants y paraissent tous
deux inutiles — mais le classement des blocs reste bon, et c'est tout ce que le ciblage
des mutations utilise. Shapley reste disponible (`attribution_method: shapley`) pour une
analyse ponctuelle hors boucle, et les deux méthodes partagent le même cache : basculer
de l'une à l'autre ne jette aucune évaluation déjà payée.

**Avant :** une passe d'attribution ≈ 25 × N évaluations → quota épuisé en une journée
**Après :** N+1 évaluations, budget prévisible → la boucle tourne jusqu'au bout

---

## [2026-07-29] Les agents ne suivent plus l'avis du LLM, ils tirent leur mode au sort

Le LLM ne désigne plus l'itinéraire optimal : il note **chaque** option proposée par la
probabilité que ce persona la retienne (somme = 100), et l'agent tire son mode dans cette
distribution. Un persona qui hésite entre voiture (60 %) et bus (40 %) ne prend plus
systématiquement sa voiture : à l'échelle de la population, les 40 % de bus existent enfin.

Le post-traitement projette ces probabilités sur une liste **fermée** de modes (marche,
vélo, voiture, transports collectifs, train, deux-roues motorisé) : un mode qu'aucune
option ne propose — la marche quand le trajet est trop long — apparaît explicitement à
**0 %** au lieu de disparaître, ce qui rend les répartitions comparables d'un agent et
d'un jour à l'autre.

Le cache sémantique conserve désormais **la distribution, pas la décision**. Un cache hit
rejoue donc un tirage : le même agent, replacé dans le même contexte un autre jour, peut
prendre le bus là où il prenait sa voiture — sans le moindre appel LLM. La graine du
tirage dérive de `(agent.mode_draw_seed, agent, activité, jour simulé)` : un run relancé
reproduit exactement les mêmes trajets, et changer `mode_draw_seed` explore un autre
tirage sans repayer d'inférence.

Chaque demande d'itinéraire trace sa répartition dans `moves.csv`, **une colonne par
mode** (`P(Marche) %`, `P(Voiture Privée) %`, …) : on peut comparer ligne à ligne ce que
le LLM estimait et ce que l'agent a fait, et agréger les parts modales attendues sans
reparser quoi que ce soit. Un `0` signifie « mode explicitement écarté », une cellule vide
« décision sans répartition » (mono-choix, erreur LLM, cache hérité).

Côté calibration de prompt, l'évaluation applique la même politique — et les
`eval_samples` tirages proviennent maintenant d'un **seul** appel LLM : une éval `train`
coûte 33 requêtes au lieu de 99, à nombre de décisions scorées identique.

**Avant :** un persona = un mode figé ; un cache hit rejouait éternellement la même décision
**Après :** un persona = une distribution ; chaque cache hit retire un mode, la répartition
attendue est visible dans `llm_mode_probability_pct_total`

⚠ Deux invalidations attendues : le texte des prompts système ayant changé, le **cache LLM
repart d'un répertoire neuf** (il est isolé par empreinte de prompt), et les évaluations de
calibration déjà payées ne sont plus réutilisables.

---

## [2026-07-28] La boucle cesse d'ordonner au mutateur de s'entêter

Un rejet annoté `Δ=+9.89` — le candidat **aggrave** l'écart de 23 % — était classé
« bruit statistique », catégorie dont la consigne associée est « l'idée n'est pas
invalidée, garde le levier ». La boucle demandait donc de persévérer sur une piste que
la mesure venait de réfuter. En campagne 7, cinq itérations consécutives ont reformulé
le même levier sur le même bloc, pour rien.

Les rejets sont désormais triés par **ampleur** : au-delà de 10 % du score courant, un
échec devient `[dégrade]` et déclenche la consigne inverse — abandonner le levier, pas
le reformuler. En dessous, rien ne change : une amélioration non significative reste une
piste ouverte.

**Avant :** `Δ=+9.89` et `Δ=+0.30` recevaient la même consigne
**Après :** les dégradations franches disent « change d'hypothèse », les Δ marginaux
disent toujours « reformule »

---

## [2026-07-28] Le prompt d'optimisation ne peut plus enseigner ce qu'il interdit

La règle « jamais de seuil chiffré du type *marche si moins de 2 km* » n'était qu'une
phrase adressée au modèle : rien ne l'appliquait. Un bloc contenant exactement cette
règle avait donc été accepté, puis **capitalisé comme meilleur argument de la
bibliothèque** (gain 134.4), puis re-servi à chaque itération comme exemple à imiter.

La contrainte est maintenant appliquée en code, avant toute évaluation, et les arguments
capitalisés qui la violent sont écartés — y compris ceux déjà stockés, sans avoir à
toucher aux bases existantes. La *mention* d'un nombre reste permise : « la règle des
48 heures » passe, « moins de 2 km » non.

**Pourquoi ça compte :** un seuil chiffré fait du choix de mode un automatisme. Le
prompt cesse alors de simuler un raisonnement de déplacement et encode la réponse
attendue — il colle au jeu d'évaluation et ne vaut plus rien en simulation.

---

## [2026-07-28] Le bloc à modifier est choisi par calcul, plus par le modèle

Désigner le bloc de prompt le plus nuisible n'est pas un jugement : c'est un maximum sur
des grandeurs déjà mesurées (contribution Shapley, poussée modale, strates fautives).
Ce choix est passé du modèle au code, ce qui libère de la place dans le prompt et rend
la décision reproductible.

Un bloc rejeté deux fois de suite sort maintenant du jeu des cibles pour trois
itérations. L'ancien garde-fou ne bloquait que la répétition d'un **texte** proche,
jamais l'acharnement sur une **cible** — c'est ce qui laissait un même bloc monopoliser
la campagne pendant que des blocs nuisibles jamais essayés attendaient leur tour.

**Avant :** cinq itérations d'affilée sur `consigne_s3`
**Après :** ce bloc passe en cooldown et la cible bascule sur le bloc nuisible suivant

---

## [2026-07-28] Mutation en deux temps : diagnostiquer, puis rédiger

Le prompt d'optimisation demandait au modèle d'analyser ses échecs, de choisir sa cible
et d'écrire le texte dans le même souffle, avec tout le contexte servi d'un bloc. On
peut désormais scinder : un premier appel diagnostique le bloc visé et produit une
directive courte (il lui est interdit d'écrire le texte), un second rédige sous cette
directive sans revoir l'appareil analytique.

Chaque appel est nettement plus court : le plus long passe de 15 600 à 6 800 caractères,
et les **deux réunis** coûtent moins que l'appel unique d'avant. L'appel supplémentaire
se paie sur le quota du modèle de mutation, distinct de celui de l'évaluation.

Désactivé par défaut (`decomposed_mutation`), pour être comparé au fonctionnement
historique à budget d'évaluation égal plutôt que substitué en silence.

**Avant :** un appel de ~15 600 caractères qui fait tout
**Après :** deux appels spécialisés, 0,57× le coût en texte, ablatables séparément

---

## [2026-07-27] Le pré-tri par un second modèle est abandonné

Mesure décisive : sur 23 mutations d'un même prompt, le modèle léger pressenti pour
pré-trier les candidats **ne retrouve pas du tout le classement du juge de référence**
(corrélation de rang −0,01, soit l'équivalent d'un tirage au sort). L'idée d'essayer
plusieurs mutations par itération et de laisser un modèle bon marché désigner la
meilleure est donc écartée.

Ce résultat corrige une mesure antérieure encourageante (corrélation 0,76), obtenue
sur des prompts très différents les uns des autres. Départager des variantes franches
est facile ; départager des candidats **voisins** — la seule chose utile pour un
pré-tri — ne fonctionne pas.

**Avant :** on envisageait 3 ou 4 candidats par itération avec pré-sélection automatique
**Après :** un seul candidat par itération, comme aujourd'hui ; le second modèle reste
utile uniquement pour *générer* les mutations, ce qui libère déjà le quota du juge

---

## [2026-07-27] Nouvelle pénalité de longueur : tolérance puis coût exponentiel

La pénalité de longueur peut désormais prendre une forme à seuil : **nulle jusqu'à
une taille de prompt jugée acceptable** (350 mots par défaut), puis croissante de
façon exponentielle au-delà. Dans la zone de tolérance, deux prompts ne sont plus
départagés que par la qualité de leur prédiction ; au-delà, le coût devient vite
prohibitif, ce qui empêche le prompt de s'allonger sans fin.

Rejouée sur les 173 évaluations déjà en base, la correction remet le classement à
l'endroit : le prompt vidé de ses instructions passe du 1ᵉʳ au 7ᵉ rang, et le
meilleur devient un prompt de 7 blocs et 179 mots. La corrélation entre longueur et
score tombe de 0,81 à 0,02 — la longueur cesse d'être un critère de sélection.

**Avant :** un prompt de 335 mots encaissait 16,75 points de pénalité d'entrée
**Après :** 0 point tant qu'il reste sous le seuil ; 2 points à 500 mots, 20 à 650

L'ancienne forme linéaire reste disponible et reste le défaut ; la nouvelle
s'active par `length_penalty_mode: exp_tolerance`. Le changement ne coûte aucun
appel LLM et n'invalide aucune évaluation déjà payée.

---

## [2026-07-27] La calibration optimisait la brièveté plus que la justesse

Le meilleur prompt du store s'est avéré être… le prompt vide. En décomposant la
métrique, la cause est identifiée : la **pénalité de longueur** pèse autant que le
terme de fidélité aux parts modales, et représente environ 40 % de la variation
totale du score.

Or la taille du prompt n'a **aucun effet mesurable sur la qualité de prédiction**
(corrélation de rang −0,03 sur 173 évaluations, non significative) : les
répartitions de modes prédites sont quasi identiques du prompt vide au prompt
complet. Tout ce que le score retenait de la longueur venait de la pénalité.

Recalculé sans elle, le classement s'inverse : le meilleur prompt passe de 1 bloc
à 7 blocs, et les deux classements ne se ressemblent qu'à moitié.

En revanche — et contrairement à ce qu'on pouvait attendre — ce n'est **pas** ce qui
bloque la campagne en cours (19 mutations, 0 acceptée). Vérification faite sur les
couples avant/après disponibles : toutes les mutations proposées *raccourcissent* le
prompt, donc la pénalité les avantage, et toutes dégradent quand même la prédiction.
Annuler la pénalité n'en sauverait aucune. Le blocage vient du générateur de
mutations, qui ne produit que des candidats moins bons.

**Avant :** le score récompensait surtout les prompts courts
**Après :** le diagnostic est posé et chiffré ; le dosage de la pénalité reste à trancher

Le réglage se teste **sans aucun appel LLM** (`make backtest`) : les décisions brutes
sont conservées et le dosage de la pénalité n'entre pas dans la clé de cache.

---

## [2026-07-27] Analyse Shapley sur la marche — et une fuite de données dans ProGEDO

Un troisième notebook, `scripts/progedo_logit/explore_progedo_walk_shapley.ipynb`, applique à
la **marche** le protocole du notebook vélo. Il en ressort deux choses : un avertissement sur
les données, et un diagnostic inverse de celui du vélo.

### Deux variables ProGEDO sont inutilisables pour la marche

Les premiers modèles atteignaient une PR-AUC de **0.98** contre un taux de base de 0.31 —
aucun modèle de choix modal ne prédit un comportement social à ce niveau. La cause est
identifiée : **`D11`, documentée comme distance à vol d'oiseau, n'est pas mesurée pour les
déplacements à pied. Elle vaut exactement `durée déclarée × 58 m/min`.** Rapport constant à 58
sur tous les quantiles, ~250 valeurs distinctes contre ~9 800 pour la voiture, corrélation avec
la géographie réelle de 0.40 pour la marche contre 0.995 pour les autres modes. La variable
n'encode pas une distance : elle encode la cible. `D12` (distance sur le réseau du mode
utilisé) est contaminée pour la même raison.

Le notebook les remplace par une distance reconstruite depuis le shapefile des zones fines,
identique quel que soit le mode. La PR-AUC retombe alors à une valeur crédible.

**Avant :** PR-AUC marche = 0.985, artefact de mesure
**Après :** PR-AUC marche = 0.804 (baseline) à 0.855 (41 variables), sur une distance
origine-destination mode-neutre

⚠️ **Le notebook vélo utilise `D11` et est donc concerné** : sa PR-AUC de 0.410 est
probablement surestimée, les trajets à pied y étant identifiables à coup sûr. Le classement
SHAP reste vraisemblablement valide. Un rejeu avec la distance corrigée est à faire.

### La marche est contrainte, le vélo est choisi

Une fois la fuite corrigée, enrichir le persona n'apporte presque rien à la marche : **×1.06**
contre ×1.78 pour le vélo. La marche est décidée par la géométrie du déplacement, et se
modélise sans persona riche pourvu que l'agent dispose d'une distance origine-destination
correcte.

À 2 km ou moins — là où les quatre modes sont plausibles et où un levier a un sens — les
déterminants apparaissent : le **motif** (le loisir pousse à marcher, le travail non), la
**disponibilité d'une voiture** (même variable clé que pour le vélo, et même sens : les modes
actifs se décident contre la voiture), le **nombre de voitures par titulaire du permis**, le
**type d'habitat** (la maison isolée décourage la marche) et le **stationnement nocturne de la
voiture** — quand la reprendre coûte une place au retour, on marche. L'âge joue en U : 72 % de
marche chez les 17–25 ans, 70 % chez les 75 ans et plus, 57 % chez les 40–60 ans.

Comme pour le vélo, la catégorie grossière `car_availability` ne pèse presque rien (0.021)
quand le comptage fin en pèse dix fois plus : **l'agrégation en catégories détruit le signal**.

### Conséquence pour la mémoire de l'agent

Les habitudes déclarées ne captent que **11,1 % de l'importance SHAP** pour la marche, contre
28,6 % pour le vélo. La lecture doit rester prudente — `P19`, la fréquence d'usage de la
marche, est *intégralement vide* dans le fichier Toulouse 2023, donc l'habitude piétonne n'a
pas été mesurée. Mais le fait solide tient : les variables exogènes **suffisent** pour la
marche. La mémoire long terme est un levier pour le vélo, pas pour la marche — inutile de
dépenser du budget de contexte à raconter l'historique piéton d'un agent.

---

## [2026-07-27] Un second modèle pourrait pré-trier les candidats — sous réserve

Mesure : sur 27 versions de prompt déjà notées par le modèle juge, un second modèle
plus léger retrouve **le même classement à 76 %** (corrélation de rang de 0,758).
De quoi écarter l'hypothèse qu'il jugerait au hasard.

Ce n'est pas encore une validation. L'intervalle de confiance va de 0,53 à 0,89 :
il reste environ 30 % de chance que la vraie valeur soit sous le seuil retenu (0,70).
Et le test portait sur des prompts très différents entre eux, alors que la tâche
réelle consiste à départager des variantes proches — donc plus difficile. Le
pré-tri automatique n'est pas activé ; une seconde mesure sur des mutations réelles
tranchera.

À noter aussi : les notes des deux modèles diffèrent de 3 points en moyenne, un
écart comparable à leur dispersion. Le second modèle peut servir à *classer*, jamais
à produire une note versée dans la campagne.

La mesure n'a rien coûté au budget du juge (ses 27 notes venaient du cache) et n'a
touché aucune évaluation existante.

---

## [2026-07-27] Le modèle d'évaluation restera sur son nom actuel

Test direct sur l'API Google : le nom `…-flash-lite-preview` utilisé par la calibration
et le nom `…-flash-lite` **désignent le même modèle** — Google redirige l'un vers
l'autre. Renommer donnerait donc des résultats identiques tout en jetant toutes les
évaluations déjà payées. L'opération est écartée : coût pur, bénéfice nul.

La note de référence précise aussi que le jeu `screen` est un **échantillon gelé de 17 %
de `train`**, et qu'il sert à deux phases différentes (attribution Shapley et tri des
mutations) — une distinction qui manquait et qui rendait les chiffres d'activité de la
campagne difficiles à interpréter.

---

## [2026-07-27] Note de référence sur les quotas, et check_phase0 réparé

Une note `prompt_calibration/docs/quotas-et-modeles.md` chiffre ce que coûte
réellement une journée de calibration : une évaluation complète mobilise 297 requêtes,
soit **la totalité du quota quotidien d'un modèle**. C'est ce qui explique le rythme
d'environ une évaluation complète par jour. Le document liste aussi les quatre réglages
à ne jamais modifier sans précaution — ceux qui rendraient inutilisables toutes les
évaluations déjà payées.

Le script `check_phase0.py` ne démarrait plus depuis que la calibration est devenue un
dépôt autonome : ses imports pointaient vers l'ancienne arborescence. Il retrouve aussi
seul le répertoire d'expérience, que les deux dépôts soient imbriqués (poste de dev) ou
côte à côte (VM cloud), et affiche un message clair au lieu d'une trace quand il ne
trouve rien.

**Avant :** `check_phase0.py` s'arrêtait sur `ModuleNotFoundError`
**Après :** il tourne et confirme 100 % des sections rattachées (436 agents)

---

## [2026-07-27] Mutation et évaluation sur deux quotas Gemini séparés

La calibration disposait de 500 requêtes Gemini par jour, partagées entre l'évaluation
(le juge qui mesure la qualité d'un prompt) et la mutation (qui propose les variantes à
tester). Chaque mutation mangeait donc du budget d'évaluation. La mutation bascule sur
`gemini-3.5-flash-lite`, un modèle distinct doté de **son propre compteur de 500
requêtes/jour** : le juge garde désormais son quota entier.

Le modèle d'évaluation, lui, ne bouge pas — en changer invaliderait toutes les
évaluations déjà payées et rendrait les scores incomparables. Le cache est intact
(91 évaluations sur la base cloud, 194 en local, toutes toujours servies).

Le plafond de débit passe aussi de 15 à 12 requêtes/minute : le tableau de bord Google
montrait des pics à 18/min, donc des refus (429) en cours de campagne.

**Avant :** 500 requêtes/jour pour évaluer *et* muter ; pics de débit en dépassement
**Après :** 500 requêtes/jour dédiées à l'évaluation + 500 pour la mutation ; plus de dépassement

---

## [2026-07-25] Pourquoi le vélo est mal prédit : analyse Shapley sur ProGEDO élargi

Un second notebook, `scripts/progedo_logit/explore_progedo_bike_shapley.ipynb`, cherche les
variables qui expliquent réellement le choix du **vélo** — le mode que le modèle de choix
modal prédisait le plus mal. Là où le notebook de production ne retient que les traits
*communs* avec le persona LLM, celui-ci ratisse un maximum de variables ProGEDO et laisse
une analyse de Shapley trancher. Le notebook de production reste inchangé et comparable.

Le diagnostic est confirmé : le vélo souffrait de **variables manquantes**, pas seulement de
sa faible part modale (3,9 %).

**Avant :** 15 variables, PR-AUC vélo = 0.230
**Après :** 42 variables exogènes, PR-AUC vélo = 0.410 — **×1.78 à modèle et protocole
identiques**. 15 des 25 premières variables du classement SHAP étaient absentes du modèle.

Ce qui pèse, par ordre d'importance : la **disponibilité d'une voiture pour le trajet
domicile-travail** (le vélo se choisit contre la voiture), le **nombre de vélos par personne**
du ménage (l'ancien booléen `has_bike` détruisait cette information), la **géographie**
(densité et distance au centre, à l'origine comme à la destination — un axe totalement absent
jusqu'ici), la **saison** (5,05 % de vélo en septembre contre 3,05 % en février) et le
**niveau d'études** (de 0,17 % à 5,90 % de part vélo).

Deux enseignements contre-intuitifs. Le stationnement vélo au domicile, déterminant canonique
dans la littérature, finit 38ᵉ sur 42 : 79 % des ménages toulousains en disposent, la variable
ne discrimine pas. Et le stationnement voiture au travail **s'inverse** une fois les autres
variables contrôlées — son effet brut était porté par des corrélats, pas par lui-même.

Enfin, un résultat qui porte sur l'architecture de l'agent plutôt que sur les données : en
ajoutant les **habitudes déclarées** (fréquence d'usage du vélo, de la voiture, des TC), la
PR-AUC monte à 0.601 et la fréquence d'usage du vélo devient la première variable du modèle,
devant la distance. Cinq variables captent 28,6 % de l'importance totale. Une part
substantielle du signal vélo n'est donc pas structurelle mais **habituelle** — elle réside
dans l'historique de la personne, c'est-à-dire précisément ce que la mémoire long terme de
l'agent est censée porter. Un agent sans mémoire des trajets passés a un plafond de
performance sur le vélo, quelle que soit la richesse de son persona.

Métrique employée : PR-AUC (et non l'accuracy, sans signification à 3,9 % de positifs),
séparation train/test **par ménage** pour éviter qu'un même individu figure des deux côtés.

---

## [2026-07-25] Jeu ProGEDO prêt pour régression logistique (choix modal)

Un notebook extrait de l'enquête ProGEDO 2023 (EMC² Toulouse) un CSV directement exploitable
en **régression logistique multinomiale du choix modal**, en n'utilisant **que les paramètres
communs** avec le persona du projet (`traits_json`) — ou rendus communs par recodage vers le
même espace de valeurs. Une ligne = un déplacement (l'unité de décision de l'agent), la cible
est le mode `car/bike/walk/transit` (aligné sur `_primary_mode`).

Les features couvrent le persona statique (âge, sexe, taille du ménage, permis, abonnement TC,
nombre de voitures, disponibilité voiture, présence de vélo, catégorie socioprofessionnelle,
occupation, emploi/études) et le contexte de décision (motif, distance, heure de départ).
`income` et `employment_sector` sont exclus (absents de ProGEDO) ; `personal_bike` est réduit à
`has_bike` car les vélos électriques (M22) ne sont pas renseignés dans ce jeu.

Le notebook fait import → merge (déplacement + personne + ménage) → recodage → nettoyage
(modes hors champ, non-enquêtés, valeurs critiques manquantes) → séparation features/cible →
export, et se termine par un contrôle sklearn qui ajuste le CSV tel quel.

**Avant :** les CSV ProGEDO bruts (codes SAS, une table par niveau) n'étaient pas alignés sur
le vocabulaire du persona ni structurés pour un modèle de choix modal.
**Après :** `scripts/progedo_logit/progedo_mode_choice.csv` (~54 500 déplacements, 15 features +
cible) prêt à charger, plus les variantes `_X.csv` / `_y.csv`.

---

## [2026-07-24] Calibration : notifications Discord détaillées (« où en est la campagne »)

Les notifications du daemon de calibration disaient **qu'il** travaillait, jamais **où il
en était** : entre « Daemon démarré » et « Quota épuisé », des heures de silence, sans
savoir s'il en était à la dixième ou à la deux-centième coalition Shapley. Le salon
Discord suit désormais la campagne **étape par étape**.

Au **démarrage** de chaque passe, un message « d'où l'on part » : itération de reprise et
cible, meilleur composite connu, prompt courant (score, nombre de mots, blocs mutables),
tailles des jeux train/val/screening, modèle d'éval et nombre de coalitions Shapley
attendues. À l'**arrêt** (quota épuisé ou budget atteint), le message symétrique : l'étape
exactement interrompue, le travail de la passe (itérations, acceptées/rejetées, évals
payées vs servies par le cache, appels LLM, durée) et le gain de composite obtenu.

Entre les deux, les **étapes principales** sont annoncées (éval initiale, proposition de
mutation, gate de strate, screening, paliers de racing, éval complète, attribution
Shapley, validation, compaction), chaque **itération** publie sa mutation puis son verdict
(composite, Δ, cause de rejet), et un **battement de cœur** (toutes les 15 min par défaut)
donne l'avancement *à l'intérieur* d'une étape longue — c'est lui qui répond à « il en est
où, sur ses 250 valeurs de Shapley ? ».

**Avant :** « 🟢 Daemon démarré » … 6 h de silence … « ⏸️ Quota épuisé — reprise demain 07:00 »
**Après :** « ▶️ Passe démarrée — itération 11 → 50, best 36.80 » … « 🔷 Shapley (init) 253
coalitions attendues » … « ⏳ Avancement — Shapley 124/253 (49 %), 87 payées, 37 cache » …
« ⚖️ Itération 12 → accepted, composite 34.20 (Δ=-2.60) » … « ⏸️ Quota épuisé pendant :
attribution Shapley après acceptation #5 · 168/253 (66 %) — 3 itérations, 412 évals payées »

Réglable dans la config du run (`notify_stages`, `notify_iterations`,
`notify_heartbeat_seconds`, `notify_min_interval_seconds`) ; sans webhook Discord, rien ne
change et rien n'est envoyé.

---

## [2026-07-23] Calibration : notifications Discord & digest quotidien

Le daemon de calibration autonome peut désormais **remonter son état sur un salon
Discord**, pour suivre une campagne cloud sans SSH. Un webhook (pas de bot) reçoit
**uniquement les transitions d'état** : démarrage, quota épuisé → mise en veille (avec
l'heure de reprise), reprise après reset, **nouveau meilleur prompt**, fin de campagne.
Deux ajouts qui ciblent des angles morts : une alerte **⚠️ quand un 429 n'est pas
identifié « per day »** (le cooldown retombe alors sur un délai court — signe que le
libellé Gemini a peut-être changé), et une alerte **☠️ « daemon mort »** portée par
systemd (`OnFailure=`), seul moyen de prévenir en cas de crash/OOM où plus aucun message
applicatif ne peut partir.

Nouveau `calibrate digest` (timer systemd quotidien) : un **récapitulatif lisible**
(itération, meilleur composite, évals payées et mutations acceptées sur 24 h, veille en
cours) **reformulé par Mistral** — modèle distinct du quota d'éval Gemini, donc **sans
entamer le budget** de la campagne ; repli sur un texte brut si Mistral est indisponible.

Le tout est **best-effort et opt-in** : sans `DISCORD_WEBHOOK_URL` dans `~/calib.env`,
aucune notification n'est émise (no-op) ; un envoi qui échoue n'interrompt jamais la
campagne (le store SQLite reste la source de vérité). Aucun contenu de prompt ni clé
n'est transmis — seulement des métriques agrégées.

**Before :** campagne cloud silencieuse — il fallait `journalctl -u calib` en SSH pour
savoir si elle avançait, dormait ou était morte.
**After :** l'essentiel arrive sur Discord (veille/reprise/best/fin/échec) + un digest
quotidien ; la supervision SSH devient optionnelle.

---

## [2026-07-23] Calibration : daemon autonome & cooldown quota (24h/reset)

La calibration de prompt peut désormais tourner **entièrement seule sur le cloud** et
exploiter au mieux le quota journalier (RPD/TPD). À l'épuisement du quota, les requêtes
LLM sont **mises en veille jusqu'à la réouverture du quota** — la durée est lue dans le
429 du provider, avec une subtilité : pour un quota **journalier** (marqueur `PerDay`),
le délai renvoyé par Gemini sous-estime le temps réel jusqu'au reset, donc on vise le
**prochain minuit Pacific** (`quota_reset_tz`, DST géré) pour reprendre pile sur le quota
frais. Le cooldown est **persisté dans le store** (portée globale), donc il survit à un
redémarrage.

Nouveau mode `calibrate run --loop` : un **daemon** qui dort pendant le cooldown
(heartbeat `💤` dans les logs) puis reprend seul — plus besoin de cron. Une unité systemd
(`cloud/calib.service`) le maintient en vie (démarrage au boot, redémarrage après crash).
Le lancement cron one-shot reste supporté et bénéficie de la même **garde de démarrage**
(il sort proprement si un cooldown est encore actif au lieu de re-solliciter l'API).

**Avant :** quota épuisé → le run s'arrêtait ; il fallait un cron externe pour rejouer,
et une relance trop tôt re-tapait l'API avant le reset.
**Après :** `run --loop` sous systemd → la campagne consomme le quota du jour, se rendort
jusqu'au reset, reprend, et progresse jusqu'à `max_iterations` sans supervision.
Réglages : `quota_reset_tz`, `cooldown_fallback_seconds`, `cooldown_max_seconds`,
`daemon_sleep_chunk_seconds`.

---

## [2026-07-22] Calibration : arrêt propre à l'épuisement du quota

La boucle de calibration de prompt peut désormais s'arrêter proprement quand le quota
journalier du provider d'éval est épuisé, au lieu de marteler l'API en boucle sur des
coalitions vouées à l'échec. Un coupe-circuit compte les échecs de lot **consécutifs**
(paramètre `eval_max_consecutive_errors`, défaut 3) : tout succès remet le compteur à
zéro, donc une coupure réseau transitoire isolée ne l'arrête pas — seule une salve
franche (quota mort) le fait. À l'arrêt, le cache est intact : relancer le run reprend
exactement à la première coalition non payée.

**Avant :** quota épuisé → le run continuait des heures, chaque coalition rejouant 5
retries × N lots en pure perte, jusqu'au `Ctrl-C` manuel (trace Python en prime).
**Après :** au 3ᵉ échec consécutif, message `🛑 … quota probablement épuisé`, arrêt
propre sans trace, reprise gratuite au run suivant. `eval_max_consecutive_errors: 0`
rétablit l'ancien comportement.

---

## [2026-07-21] Quotas Gemma corrigés : +90 % de budget journalier, TPM enfin borné

Les deux providers Gemma (`google_gemma42` / `google_gemma43`) étaient déclarés avec des quotas
free tier erronés. Relevé sur le dashboard AI Studio, le réel est **RPM 30 · TPM 16 000 · RPD
14 400** par modèle — la config annonçait `rpm 15`, `tpm null` (« illimité ») et `rpd 1500`.

Deux effets concrets :
- **Budget journalier** : chaque Gemma passe de 1 500 à 14 400 requêtes/jour. À eux deux ils offrent
  désormais ~28 800 req/j, de loin le plus gros pourvoyeur free tier (vs 500/j pour gemini-3.1-flash-lite).
- **Anti-saturation** : le TPM était déclaré illimité, donc le load-balancer envoyait de gros batchs
  aux Gemma alors qu'ils plafonnent à 16 000 tokens/min (≈ 5 agents de 3k tokens). Le TPM réel est
  maintenant renseigné : les batchs s'auto-dimensionnent et un `max_tokens_per_request` évite les
  HTTP 413. Le `weight` tombe de 1.0 à 0.36 (les Gemma sont bornés par le TPM, comme Groq).

**Avant :** Gemma bridés à 1 500 req/j et réputés à TPM illimité → budget gâché + risque de saturation.
**Après :** Gemma exploités à 14 400 req/j chacun, débit tokens correctement borné.

---

## [2026-07-22] Calibration : poids du composite auditables (sensibilité, zéro LLM)

Les poids du composite étaient posés à la main (`global 1.0, âge 0.5, genre 0.3…`) et
mélangeaient l'**échelle** d'un terme (une L1 sur 15 tranches d'âge et une JSD n'ont pas
la même magnitude) et son **importance**. Deux ajouts, sans aucun appel modèle :

- Les losses acceptent désormais des **poids par instance** (`weights=`) ; le composite
  reste linéaire (Shapley/backtest inchangés).
- Nouvelle commande **`calibrate weights`** : reclasse les prompts déjà évalués sous
  plusieurs schémas de pondération — `uniform`, `informativity` (dérivés du pouvoir
  discriminant de chaque axe dans EMC²), `scaled` (**normalisation d'échelle** par le
  prompt seed), `strat_x2` / `strat_half` — et dit si le **meilleur prompt reste le
  meilleur** (stabilité + corrélation de rang). Répond de façon chiffrée à « pourquoi
  0.3 pour le genre ? ».

**Avant :** impossible de savoir si le classement des prompts tenait aux poids choisis.
**Après :** `calibrate weights` le vérifie en une commande, sur les décisions déjà
stockées (zéro token). *(Sur la campagne actuelle : classement STABLE, corrélations de
rang 0.96–1.0 — le gagnant ne dépend pas de la pondération.)*

---

## [2026-07-21] Calibration : mise en page du message de mutation resserrée

Le message envoyé au modèle de mutation est réordonné pour coller à sa lecture naturelle :
- La **Mémoire des leçons** passe **après** l'« Historique des mutations » (en-tête renommé
  « Historique des mutations et enseignements »), dont elle est le prolongement — au lieu d'être
  intercalée avant.
- Le rappel `💡 Opérateur à privilégier ce tour` **clôt** désormais le message (juste après la
  consigne JSON), au lieu d'être noyé entre le prompt complet et l'instruction.
- La section « ⚖️ Diversité des cibles » est **supprimée** : le garde-fou anti-resoumission
  (tabu + prescreen) empêche déjà de re-toucher trivialement le même bloc, la consigne faisait
  doublon.

**Avant :** leçons avant l'historique, rappel d'opérateur au milieu du message, section diversité
en plus.
**Après :** historique → enseignements, prompt complet, instruction, puis opérateur suggéré en
dernière ligne ; message plus court et plus lisible.

---

## [2026-07-21] Calibration : liste des opérateurs et coût-mot rappelés dans la consigne de mutation

La consigne finale envoyée au modèle de mutation (`build_mutation_user_msg`) rappelle désormais
explicitement, juste avant le JSON attendu : (1) les **7 actions possibles** (`modify`, `delete`,
`insert`, `condense`, `reorder`, `merge_blocks`, `split`) avec un résumé d'une ligne chacune ;
(2) le **coût de longueur** — chaque mot du prompt ajoute 0.05 pt d'écart (`length_penalty`), donc
à effet égal la formulation la plus courte est préférée. Vaut pour les deux chemins (candidat
unique et multi-candidats).

**Avant :** la palette d'opérateurs n'apparaissait que dans le prompt système ; la consigne finale
ne mentionnait que « modify » (l'exemple de JSON), et l'incitation à la concision n'était pas rappelée
au moment de proposer.
**Après :** le mutateur voit la liste complète des actions et le coût-mot à l'endroit où il rédige sa
proposition — il exploite mieux `condense`/`delete`/`merge_blocks` et raccourcit à effet égal.

---

## [2026-07-21] Calibration : `emd_jsd` devient la loss par défaut

La métrique par défaut d'une campagne de calibration est désormais `emd_jsd` (EMD ordinal
sur âge/distance + JSD nominal sur global/occupation/genre/motif + pondération continue par
effectif), y compris quand aucun `loss` n'est précisé. Tous les fichiers de config
l'utilisaient déjà ; seul le défaut codé dans `RunConfig` restait sur l'ancienne `l1_composite`.

**Avant :** une campagne lancée sans `loss` explicite tombait sur `l1_composite` (toutes les
catégories traitées comme interchangeables — un glissement d'âge adjacent coûtait autant qu'un
glissement lointain).
**Après :** défaut `emd_jsd`, qui respecte l'ordre des dimensions ordinales. `l1_composite`
reste sélectionnable et recalculable rétroactivement en backtest.

---

## [2026-07-21] Calibration : contexte du mutateur refondu (« ingénieur prompt »)

Le message envoyé au modèle de mutation (calibration du prompt) a été réécrit pour aller à
l'essentiel, parler d'**écart** (et non de « score composite »), et présenter le prompt de
façon plus lisible :

- **Phrase d'intro** : le message s'ouvre sur la mission (« Tu es ingénieur prompt : ta mission
  est d'optimiser le prompt système ci-dessous… »).
- En-tête `Distribution LLM actuelle :` **sans** le compte de décisions.
- **Hard negatives supprimés** (exemples individuels persona → mode) et bloc **« DEUX leviers
  prioritaires » supprimé** : redondants avec les « pires écarts strate × mode », désormais en
  **top 10** (au lieu de 6) et **sans** l'effectif `n=`.
- Ligne `Score composite actuel` retirée ; partout on parle d'**écart**. L'historique affiche
  `écart total=… (par dimension : global …, âge …, occupation …, …)`, **en toutes lettres**.
- **Historique** borné aux **5 dernières** tentatives.
- **Mémoire de leçons** : jusqu'aux **5 dernières** synthèses de rejet (au lieu d'une seule),
  numérotées.
- **Présentation unifiée du prompt** : chaque bloc est donné **dans l'ordre**, avec son **contenu
  entier** et sa contribution (Δ écart, dimensions aidées/dégradées, effet sur les modes) **sans
  abréviations**, **blocs fixes inclus**. Cette vue remplace l'ancienne table + le dump séparé des
  blocs modifiables.
- Le rappel d'opérateur ne suggère « garde de la diversité » qu'en **multi-candidats**.

**Before :** contexte long et abrégé (compte de décisions, deux leviers, hard negatives, score
composite, table markdown + dump des blocs, abréviations `g/ag/oc`, `voit`, une seule leçon).
**After :** contexte focalisé et lisible (top 10 sans effectif, 5 tentatives, 5 leçons, prompt
présenté bloc par bloc en toutes lettres avec sa contribution), plus clair pour le mutateur.

---

## [2026-07-21] Sources réorganisées en trois dépôts git + calibration en dépôt autonome

Le code est désormais réparti en **trois dépôts git** aux responsabilités claires :

- **`llm-agents-gama`** — le projet principal (pipeline LLM, GAMA, docker, docs).
- **`prompt_calibration`** — l'outil de calibration de prompt, extrait dans son propre
  dépôt (`github.com/Ytlse/prompt_calibration`), cloné à la racine sous
  `prompt_calibration/` (auparavant `scripts/prompt_calibration/`).
- **`eqasim-llm-toulouse`** — la génération de population eqasim (`eqasim-toulouse/`).

Les deux derniers sont imbriqués à la racine du projet mais **ignorés** par le dépôt
principal (comme `eqasim-toulouse/` l'était déjà). Tous les liens vers l'ancien chemin
`scripts/prompt_calibration/` ont été réparés : montage Docker, endpoint `/calibrate`,
skill `prompt_calib_context`, doc d'architecture, scripts de déploiement cloud, et le
`Makefile`/configs internes du dépôt de calibration (venv, jeux gelés, ressources
partagées). La suite de tests de calibration (209 tests) repasse au vert.

**Before :** la calibration vivait dans `scripts/prompt_calibration/` ; après son
déplacement, le lancement depuis l'IHM GAMA (`POST /calibrate`) et `make test` étaient
cassés (chemins morts, venv introuvable, imports périmés).
**After :** `prompt_calibration/` est un dépôt autonome monté dans le conteneur
`controller` sous `/app/prompt_calibration` ; `/calibrate` et `make test` fonctionnent.

---

## [2026-07-20] Calibration : Shapley 6× moins cher (jeu screen restauré) + console lisible

Trois corrections issues du diagnostic d'une campagne réelle :

- **Jeu `screen` ajouté aux jeux gelés v1** : gelés avant la phase 4, ils n'avaient
  pas le sous-échantillon de screening — Shapley et le screening se repliaient **en
  silence** sur le train complet (99 lots ≈ 100 requêtes par coalition). Le jeu
  (83 personas, filtre déterministe `in_screen` sur le train gelé — identique à ce
  que le générateur aurait produit) ramène chaque coalition à ~17 lots : **~6× moins
  de requêtes**, ~25-30 coalitions/jour sous quota gratuit au lieu de ~5.
- **Alarme sur le repli** : si le jeu `screen` manque, le lancement affiche désormais
  `[ALARME]` avec le surcoût et le remède, au lieu de dégrader silencieusement.
- **Console désambiguïsée** : le libellé Shapley porte le hash de la coalition
  (`shapley[2b:0640c803]`) — deux coalitions de même taille ne se confondent plus ;
  chaque coalition déjà payée affiche `✓ cache : …` à la reprise, et chaque passe se
  conclut par un bilan `N payée(s), M servie(s) par le cache`.

**Avant :** à la reprise, impossible de distinguer un recalcul payant d'un cache hit ;
Shapley consommait ~100 requêtes par coalition sans signal.
**Après :** la console montre ce qui est resservi gratuitement, et Shapley tourne sur
le jeu de screening prévu par l'architecture.

---

## [2026-07-20] Calibration : Shapley cumulatif à graine fixe — mêmes tokens, plus de précision

Le recalcul Shapley après chaque mutation acceptée re-tirait des permutations
aléatoires neuves : la plupart des coalitions évaluées ne retombaient jamais sur le
cache, et chaque passe repayait des évaluations qui n'apportaient pas d'information
nouvelle. Nouveau régime **cumulatif** (activé dans les configs de campagne) :

- **Socle à graine fixe** : les mêmes permutations sont rejouées à chaque passe.
  Après une réécriture de bloc, toutes les coalitions sans ce bloc sont servies par
  le cache (zéro appel LLM) — on ne paie que ce qui contient du contenu nouveau.
- **Addon plafonné** : quelques permutations fraîches s'ajoutent à chaque mutation
  acceptée (`shapley_addon_per_accept`, plafond `shapley_max_permutations`) — la
  précision de l'attribution de crédit augmente au fil de la campagne, au moment où
  les décisions (compaction, publication) en dépendent le plus.
- **Plafond ajustable en cours de campagne** : modifier le YAML suffit, pris en
  compte à la reprise suivante sans invalider le moindre calcul déjà payé.

**Avant :** chaque recalcul Shapley repayait ~toutes ses coalitions ; précision constante.
**Après :** un recalcul après réécriture ne paie que les coalitions touchant le bloc
modifié ; la précision croît (25 → 50 permutations) pour un coût par passe borné.

L'ancien comportement reste disponible (`shapley_addon_per_accept: 0`).

---

## [2026-07-17] Calibration : lancement sur une VM Google gratuite (guide clé en main)

La campagne de calibration de prompt peut désormais tourner **toute seule sur une machine
Google Cloud gratuite** (offre « Always Free » `e2-micro`), sans quitter le poste des yeux.
Un dossier `scripts/prompt_calibration/cloud/` fournit tout le nécessaire :

- **`README_CLOUD.md`** — un guide pas à pas « pour les nuls » (création de la VM, upload
  des données, clé API, automatisation), pensé pour quelqu'un qui n'a jamais touché à
  Google Cloud.
- **`config/cloud.yaml`** — la configuration de campagne côté cloud (chemins relatifs du
  dépôt, quota free tier Gemini).
- **`setup_vm.sh`** / **`run_daily.sh`** — installation en une commande, puis un réveil
  `cron` quotidien qui reprend la campagne là où le quota du jour l'avait arrêtée.
- **`data_to_upload.tar.gz`** — les jeux gelés `v1` (hors Git) prêts à envoyer à la VM.

**Coût : 0 €.** La campagne s'étale sur plusieurs jours (500 requêtes Gemini/jour en
gratuit), mais la reprise du store SQLite fait qu'il n'y a rien à surveiller : elle avance
un peu chaque nuit jusqu'à la fin.

**Avant :** la calibration ne se lançait qu'en local (poste de dev) ou via l'IHM GAMA.
**Après :** un déploiement cloud gratuit, autonome et reprenable, documenté de bout en bout.

---

## [2026-07-17] Calibration : le mutateur voit du concret (matrice bloc × mode, exemples réels, snippets entiers)

Le mutateur de prompt ne raisonnait que sur des agrégats (distributions, écarts,
contributions par dimension). Trois évolutions lui donnent du concret — **sans aucun
appel LLM supplémentaire** (données déjà persistées, uniquement calcul et formatage) :

- **Matrice bloc × mode** : la table de contribution gagne une colonne « modes poussés »
  (ex. `vélo+4 voit-3`) — l'effet de la présence de chaque bloc sur les parts modales,
  décomposé par Shapley sur les mêmes évals. Le mutateur sait *quel mode* un bloc favorise
  ou freine, au lieu de deviner la corrélation depuis les dimensions.
- **Exemples réels de décisions à corriger** (hard negatives) : jusqu'à 4 décisions
  individuelles du prompt courant (persona → mode choisi) issues des pires strates
  sur-représentées, ex. `Femme, 30 ans, actif, travail, 1-2km → voiture (+70 pts vs cible)`.
  Réglable via `hard_negatives_k` (0 → désactivé).
- **Bibliothèque d'arguments fournie en entier** : les snippets n'étaient montrés que sur
  110 caractères — tronqués en plein argument, le mutateur devait halluciner la fin.
  Contenu complet désormais (cap de sécurité à 300).

**Avant :** le mutateur devinait la relation bloc → mode et n'avait jamais vu une erreur concrète.
**Après :** chaque tour montre qui pousse quoi, et à quoi ressemble une décision aberrante type.

---

## [2026-07-17] Calibration : attribution Shapley globale à chaque acceptation (fin du leave-one-out)

La contribution de chaque bloc au score est désormais **recalculée par attribution de
crédit Shapley après *chaque* mutation acceptée** (et à l'initialisation), sur le jeu de
screening. L'ancienne ablation *leave-one-out* (retrait d'un bloc à la fois) est
entièrement supprimée : elle supposait les blocs indépendants et se trompait sur les
blocs **redondants** (jugés inutiles à tort) et **synergiques** (crédit compté deux
fois). Shapley répartit exactement le gain entre les blocs, ces deux cas compris.

**Avant :** ablation locale rapide (leave-one-out) du seul bloc touché après chaque
acceptation, et recalcul Shapley global seulement toutes les 5 acceptations — la carte
de contribution montrée au mutateur pouvait être partiellement périmée entre deux
recalculs globaux.
**Après :** carte de contribution Shapley **complète et à jour à chaque acceptation**.
Le coût reste maîtrisé : le cache adressé par contenu du store rend gratuites les
coalitions déjà évaluées (entre permutations, entre acceptations, entre runs).

Options de configuration retirées : `shapley_enabled`, `shapley_every`,
`global_ablation_every` (le comportement est désormais unique). `shapley_permutations`
(=25) et `shapley_truncation_tol` (=0.5) restent réglables.

---

## [2026-07-17] Calibration : le mutateur apprend de ses rejets (mémoire de leçons)

Le mutateur de prompt **synthétise désormais les raisons récurrentes de ses rejets**
avant de proposer, et cette synthèse est mémorisée puis réinjectée au tour suivant.
Objectif : rompre la boucle où le mutateur re-cible sans fin le même bloc parce que le
contexte affiché ne bougeait pas entre deux rejets.

Chaque rejet de l'historique est aussi **étiqueté par catégorie** : `[fond]` (une vraie
leçon existe — ne pas y retourner) vs `[bruit]`/`[seuil]`/`[doublon]` (l'idée n'est pas
invalidée, juste non significative — la reformuler). Ce garde-fou évite que le mutateur
abandonne à tort une piste correcte rejetée pour simple non-significativité statistique.

**Avant :** les causes brutes (`Δ=+0.30@n=25`, `motif +12`) étaient affichées mais jamais
généralisées ni distinguées ; le mutateur re-proposait souvent des variantes déjà écartées.
**Après :** une mémoire de leçons roulante (bornée, persistée, reprise gratuite) guide chaque
proposition vers un changement réellement distinct, en tenant compte de la nature du rejet.

La synthèse est produite dans le même appel que la proposition (coût quasi nul, aucun appel
LLM supplémentaire). Réglable via `reflection_enabled` / `lessons_max_chars` (désactivable
pour comparaison A/B).

**Garde-fou dur associé** : « ne resoumets jamais le même texte ni une variante triviale »
n'est plus qu'une consigne — c'est appliqué en code **quelle que soit la config**. Une
proposition sans changement réel, ou quasi identique à un rejet récent, est écartée **sans
aucune éval** (dans le chemin single-candidat par défaut comme dans l'entonnoir). Une
ré-soumission triviale redevient permise une fois le contexte changé (tenure du tabu).

---

## [2026-07-17] Calibration : évaluation des itinéraires sur Gemini

La campagne de calibration (`run.yaml`) évalue désormais les itinéraires avec
**Gemini** (`google_gemini31` / `gemini-3.1-flash-lite-preview`) au lieu de Mistral.
Le prompt calibré sera donc spécifique à Gemini — le modèle réellement servi en
production pour la décision d'itinéraire.

**Avant :** éval sur `mistral-small-latest`, mutations sur Gemini.
**Après :** éval **et** mutations sur Gemini `gemini-3.1-flash-lite-preview`.

⚠ Éval et mutation partagent maintenant le même quota provider Gemini. Si ce quota
devient contraignant, basculer `mutation_model` sur un autre modèle (ex.
`google_gemma42`) rétablit la séparation.

> Reprendre une campagne existante depuis un store calibré sur Mistral n'est pas
> valide (le cache d'éval Mistral ne s'applique pas à Gemini) : repartir d'un store
> neuf. `run2.yaml` reste volontairement sur Mistral pour comparaison.

---

## [2026-07-17] Calibration : retour à un essai unique avec paliers 25/50/75 %

La calibration de prompt (`scripts/prompt_calibration/`) évalue de nouveau **un seul
essai par itération** au lieu de quatre candidats en parallèle. Cet unique essai passe
par des **paliers progressifs à 25 %, 50 % puis 75 %** du jeu d'entraînement : dès qu'un
palier **n'améliore pas** le composite du prompt courant sur le même sous-échantillon,
l'essai est **abandonné immédiatement** (verdict `rejected_race`), sans jamais payer
l'évaluation complète ni les paliers suivants.

**Avant :** 4 candidats proposés par appel de mutation, départagés par racing/screening,
le meilleur passant l'éval complète.
**Après :** 1 candidat, filtré par arrêt précoce à 25/50/75 % — moins d'appels LLM
gaspillés sur des essais non prometteurs, trajectoire plus simple à suivre.

Nouveaux défauts : `n_candidates: 1`, `racing_enabled: true`,
`racing_rungs: [0.25, 0.50, 0.75]`. Le racing multi-candidats (gate de strate +
successive halving) reste disponible en remontant `n_candidates`.

---

## [2026-07-16] Calibration : racing ciblé par strate (successive halving)

Nouvelle stratégie de sélection des candidats dans l'entonnoir de
`scripts/prompt_calibration/`, **désactivée par défaut** (`racing_enabled: false`).
Elle remplace le *screening one-shot* — une seule mesure bruitée, jugée sur le
composite global — par un **racing multi-tours** précédé d'un **gate de strate**.

- **Gate strate.** Une itération sur `racing_target_every`, les candidats sont d'abord
  évalués **uniquement** sur la strate la plus mal représentée (ex. `genre[femme]`) ;
  ceux qui n'améliorent pas son écart sont éliminés d'emblée (`rejected_gate`). Si la
  strate est trop petite ou si le gate vide la liste, **repli global** — l'itération
  n'est jamais bloquée.
- **Successive halving.** Les survivants passent des paliers de train **croissants**
  (`racing_rungs`, ex. 15 % → 35 % → 70 % → 100 %) ; à chaque palier on ne garde que la
  meilleure moitié. Le budget d'éval se concentre sur les candidats qui tiennent.
- **Garde-fou statistique.** On ne départage jamais deux candidats trop proches
  (`racing_min_gap`) ou dont l'IC bootstrap chevauche — évite d'éliminer par malchance
  un candidat qui aurait gagné sur le train complet (`rejected_race` sinon).
- **Cache respecté.** Chaque palier passe par le store content-addressed ; seule la
  fraction complète réutilise le label `train`, donc l'éval complète du gagnant est
  servie par le cache quand la boucle la refait — le racing ne « repaie » pas l'historique.

**Avant :** un seul tirage de screening (~20 % du train) sur le composite global
désigne le gagnant ; les strates en échec ne sont jamais ciblées.
**Après (opt-in) :** budget concentré sur les candidats prometteurs et sur la pire
strate ; verdicts `rejected_gate` / `rejected_race` visibles au dashboard.

---

## [2026-07-16] Calibration : contexte mutateur plus lisible + diversité des blocs ciblés

Quatre améliorations du contexte fourni au mutateur de `scripts/prompt_calibration/`,
suite à une revue du rapport de mutation.

- **Légende unique dans le prompt système.** Les abréviations des dimensions
  (`ag=âge`, `oc=occupation`…) et les **conventions de signe** sont désormais
  définies une seule fois dans le prompt système du mutateur (`LEGEND_AND_SIGNS`),
  au lieu d'apparaître de façon conditionnelle et dispersée dans chaque section.
- **Signes explicités, en termes d'écart.** Le composite est une **perte à
  minimiser** ; un **Δ>0 = bloc utile**. Dans les colonnes, « + » = le bloc
  **rapproche de la cible EMC²** (réduit l'écart), « − » = il **creuse l'écart** —
  même orientation que Δ tot.
- **Table de contribution bloc × dimension, autoportante.** L'« analyse d'ablation »
  en crochets compacts est remplacée par une **table markdown** (`format_contrib_table`) :
  une ligne par bloc, une colonne par dimension (en-têtes explicites « nom (abrév) »,
  ex. `occupation (oc)`), + Δ total, triée par utilité. Une **légende de lecture des
  signes** est imprimée juste au-dessus de la table (dans le message utilisateur, pas
  seulement dans le prompt système) → lisible sans avoir à remonter à la légende
  globale. Le diagnostic textuel n'est conservé que pour les blocs nuisibles (canal mode).
- **Diversité des blocs ciblés.** Le mutateur avait tendance à toujours retoucher le
  même bloc (souvent le premier bullet). Le prompt rappelle maintenant les blocs
  récemment modifiés (`_recent_blocks`) et exige, en multi-candidats, un **bloc-cible
  distinct** par candidat ; l'entonnoir écarte sans éval les doublons de bloc (nouveau
  verdict `rejected_dup_block`), un `insert` restant distinct d'un `modify` du même ancrage.

Tests : 189 verts (`calibration/tests/`). La piste plus ambitieuse (racing ciblé par
strate + successive halving) est spécifiée dans `docs/racing-cible-strate.md`, à
implémenter ultérieurement.

**Avant :** légende parfois absente, signes ambigus, contribution en crochets denses,
mutations concentrées sur un seul bloc.
**Après :** légende + conventions de signe systématiques, table lisible, recherche
répartie sur des blocs variés.

---

## [2026-07-16] Makefile calibration : lancer un essai et l'interface en une commande

`scripts/prompt_calibration/` dispose désormais d'un Makefile. `make run essai3`
lance (ou relance/reprend au point d'arrêt) l'essai 3 dans sa propre branche isolée
du store, et `make ui` ouvre le dashboard Streamlit. Autres raccourcis : `status`,
`export`, `finalize`, `backtest`, `datasets`, `test`. Plusieurs essais peuvent
évoluer en parallèle sans se marcher dessus.

**Avant :** il fallait retenir et taper la ligne complète `../../llm-agents/.venv/bin/python
-m calibration.cli run --config … --branch …`
**Après :** `make run essai3` / `make ui` — la branche et la config (`runN.yaml`,
sinon `run.yaml`) sont résolues automatiquement à partir du nom d'essai

---

## [2026-07-16] Dashboard calibration : filtre d'expérience global et persistant

Le dashboard de calibration gagne un filtre **Expérience** unique dans la barre
latérale (menu de gauche) : on choisit une branche/îlot (ou « Toutes les branches »)
et **toutes les vues** s'y restreignent d'un coup — Timeline, DAG, Distribution,
Comparaison, Pareto, Run et Maintenance. Surtout, la sélection **reste en place quand
on change de page** : plus besoin de refiltrer à chaque vue.

**Avant :** le filtre de branche était local à la vue Timeline et repartait sur
« toutes les branches » à chaque changement de page ; les autres vues n'avaient aucun
filtre d'expérience
**Après :** un filtre unique en barre latérale, appliqué à toutes les vues et
mémorisé d'une page à l'autre

---

## [2026-07-15] Dashboard calibration : vue Comparaison vs vérité terrain + carte d'ablation détaillée

Le dashboard de calibration gagne une vue **Comparaison** : des graphiques en barres
confrontent les parts modales de plusieurs prompts (par défaut le prompt de départ et
le meilleur trouvé) à la **vérité terrain EMC²**, en global ou strate par strate
(âge, occupation, genre, motif, distance — un graphique par catégorie, avec les
effectifs). On voit d'un coup d'œil où un prompt calibré colle à l'enquête et où il
dévie encore, sans aucun réappel LLM (tout est reconstruit des décisions stockées).

La carte d'ablation de la vue DAG affiche désormais le **détail par dimension** de
chaque bloc (une colonne par dimension, dégradé vert/rouge), avec un garde-fou : un
détail incohérent avec le Δ du bloc (évals legacy partielles) est masqué plutôt
qu'affiché faux.

**Avant :** la vue Distribution ne montrait qu'un seul nœud, en global uniquement ;
l'ablation n'affichait qu'un Δ par bloc
**Après :** comparaison multi-prompts vs EMC² par strate ; ablation décomposée par
dimension

Corrige au passage : sélection du nœud seed dans la vue DAG (plantait sur le parent
manquant), et choix de l'éval de référence quand un nœud porte plusieurs évals train
(les artefacts sans décisions brutes sont ignorés).

---

## [2026-07-15] Calibration : impact de chaque bloc détaillé par dimension (âge, motif, …)

La carte d'ablation/Shapley fournie au mutateur ne dit plus seulement qu'un bloc est
utile ou nuisible : elle indique **sur quelles dimensions** il agit, en points de
composite, avec une légende des abréviations. Le mutateur peut ainsi réécrire un bloc
pour conserver sa dimension forte tout en corrigeant son effet secondaire, au lieu de
choisir entre le garder et le supprimer.

Cette décomposition est **gratuite** : le score composite étant une somme pondérée des
dimensions, les mêmes évaluations de coalitions (Shapley) ou d'ablation (LOO) suffisent
— zéro appel LLM supplémentaire. Les contributions sous ±1 pt sont masquées (bruit).

**Avant :** `• bloc_meteo (Δ=+4.2) : Par beau temps, envisage la marche…`
**Après :** `• bloc_meteo (Δ=+4.2) [mo+3 ag+2 | oc-2] : Par beau temps, envisage la marche…`
(légende : g=global, ab=modes absents, ag=âge, oc=occupation, ge=genre, mo=motif,
di=distance, lg=longueur — le bloc aide motif et âge, dégrade légèrement occupation)

Le détail est persisté dans le store (`ablations.scores_json` pour les lignes
`shapley`) et la légende est aussi rappelée dans l'historique des mutations.

**Rétro-compat :** à la reprise d'une campagne lancée avant cette évolution, le
détail est reconstitué automatiquement depuis le store (zéro éval) — le mutateur
voit les crochets dès la première itération reprise. Les prompts de mutation déjà
stockés (vue Timeline) restent figés tels qu'ils ont été générés.

---

## [2026-07-15] Calibration : finalisation et publication du prompt calibré

La calibration de prompt (`scripts/prompt_calibration/`) sait désormais **conclure une
campagne en une commande** : `calibrate finalize` désigne le meilleur prompt trouvé,
mesure sa qualité sur le jeu de test réservé, et le publie.

**Le chiffre publiable.** Le meilleur prompt (toutes branches d'îlots confondues) est
évalué **une seule fois** sur le jeu `test` — un jeu gelé que la boucle d'optimisation
n'a jamais vu, donc une mesure honnête et non surajustée. Le prompt de départ est
évalué sur le même jeu pour donner une comparaison **avant/après** immédiate.

**Le bilan.** La commande imprime, pour le seed et le meilleur : le score par jeu
(entraînement / validation / test) et son évolution, le détail par dimension sur le
test, le nombre de mots du prompt (avant/après), le nombre d'évaluations LLM consommées
et la durée approximative de la campagne.

**La publication.** Par défaut la commande est un **essai à blanc** (rien n'est écrit).
Avec `--write`, le prompt calibré est ajouté à `prompts.yaml` sous une clé horodatée
`calibrated_…` (aucune entrée existante n'est modifiée) ; `--activate` le rend actif.

**Before :** conclure une campagne demandait de retrouver le meilleur prompt à la main,
de l'évaluer et de le recopier dans `prompts.yaml` — sans mesure de test standardisée.
**After :** une seule commande produit le score de test publiable, le bilan avant/après
et l'écriture (optionnelle et explicite) du prompt calibré.

---

## [2026-07-15] Calibration : îlots parallèles, merge et archive de Pareto

La calibration de prompt (`scripts/prompt_calibration/`) peut désormais explorer
**plusieurs pistes en parallèle** plutôt qu'une seule trajectoire, et capitaliser les
arguments qui marchent — ce qui augmente les chances de trouver un meilleur prompt à
budget d'évaluation comparable.

**Îlots parallèles.** `calibrate run --islands 3` fait évoluer 3 branches
indépendantes dans le même historique, chacune avec sa propre boucle reprenable. Elles
avancent à tour de rôle sous le même budget de requêtes ; toutes les quelques
itérations, le meilleur prompt d'un îlot est **proposé** (jamais imposé) à l'îlot
voisin — il n'est adopté que s'il améliore vraiment ce dernier. On évite ainsi qu'une
seule mauvaise piste condamne toute la campagne.

**Merge (crossover).** Deux prompts **complémentaires** — l'un bon sur l'âge, l'autre
sur le motif — peuvent être fusionnés par le modèle de mutation en un prompt enfant qui
combine leurs forces, puis évalué comme n'importe quel candidat (deux bons parents ne
font pas toujours un bon enfant : aucun merge n'est gardé sans mesure).

**Archive de Pareto.** Le score composite écrase six dimensions en un seul chiffre ;
deux prompts au même score peuvent en réalité être forts sur des dimensions
différentes. L'archive conserve désormais tous les prompts **non dominés** (ceux
qu'aucun autre ne bat sur toutes les dimensions à la fois) — matière première des
départs d'îlots diversifiés et des parents de merge. Une nouvelle vue **Pareto** du
dashboard la rend visible (nuage de compromis + bibliothèque d'arguments).

**Bibliothèque d'arguments.** Chaque bloc ajouté ou réécrit qui apporte un gain net est
capitalisé (taggé par le mode qu'il a aidé) et resservi au modèle de mutation comme
matière à réutiliser — les îlots se fertilisent ainsi mutuellement, et une future
campagne peut démarrer avec cette banque.

**Before :** une seule trajectoire d'optimisation ; un prompt au score équivalent mais
au profil complémentaire était perdu ; les bons arguments trouvés n'étaient pas réutilisés.
**After :** plusieurs îlots explorent en parallèle, échangent leurs meilleurs prompts et
peuvent les fusionner ; les compromis non dominés sont archivés et les arguments
gagnants capitalisés.

---

## [2026-07-14] Calibration : attribution de crédit par valeur de Shapley

La calibration de prompt (`scripts/prompt_calibration/`) mesure désormais **plus
justement** ce que chaque bloc du prompt apporte au score, ce qui oriente mieux les
mutations et les suppressions.

**Le problème de l'ancienne mesure.** Jusqu'ici, l'importance d'un bloc était estimée
en le retirant seul et en regardant la variation du score (« ablation un-bloc-à-la-fois »).
Cette mesure se trompe dès que les blocs interagissent : deux blocs qui disent la même
chose paraissent chacun **inutiles** (l'autre compense) — au risque de supprimer les
deux ; deux blocs qui n'agissent qu'**ensemble** se voient chacun attribuer tout le
mérite, gonflant artificiellement leur importance.

**La correction : la valeur de Shapley.** Chaque bloc est vu comme un « joueur » dont
la contribution est moyennée sur de nombreux ordres d'ajout possibles. Le mérite total
est ainsi réparti **exactement** entre les blocs, redondances et synergies comprises.
Le calcul reste économe : échantillonnage aléatoire tronqué (on s'arrête dès que le
prompt complet est reconstitué), mené sur un petit échantillon (~20 % des trajets), et
les combinaisons déjà évaluées sont resservies gratuitement par le cache.

**Before :** l'importance d'un bloc = effet de son retrait isolé → deux blocs
redondants semblent inutiles, deux blocs synergiques semblent tous deux indispensables.
**After :** l'importance = contribution moyenne équitable → la carte des blocs utiles /
nuisibles reflète les interactions réelles, et guide mieux réécritures et compactions.

---

## [2026-07-14] Calibration : entonnoir de mutation, opérateurs riches et compaction du prompt

La boucle de calibration de prompt (`scripts/prompt_calibration/`) dépense désormais
beaucoup moins d'évaluations LLM pour progresser davantage, et sait **raccourcir** le
prompt sans dégrader le score.

**Un entonnoir au lieu d'une mutation à l'aveugle.** À chaque tour, le modèle de
mutation propose maintenant **plusieurs pistes en un seul appel**. Elles franchissent
un entonnoir qui n'évalue au prix fort que ce qui le mérite :
- **Tabu** — une piste quasi identique à une modification déjà tentée et rejetée est
  écartée immédiatement, sans aucune évaluation. Elle redevient tentable plus tard,
  une fois que le prompt a suffisamment évolué.
- **Pré-sélection rapide** — les pistes restantes sont comparées sur un petit
  échantillon (~20 % des trajets) ; seule la meilleure passe l'évaluation complète et
  le test statistique.

**La boucle apprend quels leviers marchent.** Un bandit choisit l'opérateur à
privilégier (réécrire, supprimer, insérer, déplacer, fusionner, condenser, scinder un
bloc) en fonction de ce qui a été accepté jusqu'ici — visible au dashboard.

**Le prompt est activement raccourci.** Périodiquement et en fin de campagne, une passe
de **compaction** retire les blocs qui n'apportent rien, à condition de prouver
statistiquement que le score ne se dégrade pas. Comme le prompt calibré est envoyé à
chaque décision d'itinéraire en production, chaque mot économisé est payé des millions
de fois.

**Before :** chaque itération = une mutation évaluée sur tout le train, prompt qui ne
fait que grossir.
**After :** plusieurs candidats filtrés à bas coût par tour, opérateurs arbitrés
automatiquement, et un prompt qui se raccourcit tant que le score tient.

---

## [2026-07-14] Calibration : loss ordinale (EMD/JSD) et acceptation statistique

La calibration de prompt (`scripts/prompt_calibration/`) mesure et accepte désormais
plus juste.

**Loss v2 (`emd_jsd`, au choix via `loss:` dans la config).** L'ancienne loss L1
traitait toutes les tranches comme interchangeables : rendre les 15-19 ans un peu trop
adeptes du bus vers les 20-24 ans coûtait autant que vers les 50-54 ans. La nouvelle
loss respecte l'ordre des tranches — âge et distance sont mesurés par **EMD** (coût de
déplacement le long de l'axe), un décalage vers une tranche voisine coûte moins qu'un
décalage lointain. Les critères sans ordre (occupation, genre, motif, global) passent
à la **divergence de Jensen-Shannon**, et chaque strate compte désormais au prorata de
son effectif au lieu d'être ignorée sous 5 individus.

**Acceptation statistique (bootstrap).** Une mutation n'est retenue que si son gain est
**significatif** : un rééchantillonnage des agents (bootstrap apparié) estime si
l'amélioration tient au-delà du bruit d'échantillon. Le recuit assouplit l'exigence de
significativité en début de campagne (exploration) mais **jamais le signe** — une
mutation qui dégrade le score n'est plus jamais acceptée. Les rejets « pour bruit » sont
tracés (`rejected_stat`) et renvoyés au mutateur.

**Backtest sans réappel LLM.** `calibrate backtest --metrics l1_composite,emd_jsd`
recalcule n'importe quelle loss sur tout l'historique déjà stocké (les décisions brutes
sont conservées) et compare les trajectoires — on choisit la loss en connaissance de
cause avant de basculer une campagne.

**Avant :** score L1 aveugle à l'ordre des tranches ; une mutation acceptée dès que le
composite baissait, même d'un poil sous le bruit.

**Après :** l'erreur reflète la distance réelle entre tranches ; seules les
améliorations statistiquement solides sont conservées, et toute loss est rejouable
rétroactivement sur l'historique.

---

## [2026-07-13] Dashboard de calibration : l'historique d'une campagne, explorable en direct

Le moteur de calibration de prompt (`scripts/prompt_calibration/`) a désormais un
**dashboard Streamlit**, lecteur pur du store SQLite, rafraîchissable pendant qu'une
campagne tourne. On y explore toute l'histoire d'une campagne sans notebook :

- **Timeline** : chaque mutation depuis l'origine avec son verdict et son score
  composite *et* par dimension, filtrable, avec la courbe du meilleur score ;
- **DAG** : le graphe de lignée des prompts coloré par score — un clic sur un nœud
  ouvre son prompt, le diff avec son parent, ses scores et sa carte d'ablation ;
- **Distribution** : parts modales actuelles vs cible EMC² et pires croisements
  strate × mode, reconstruits depuis les décisions brutes (aucun appel LLM) ;
- **Run** : itération, meilleur score, modèles/températures, volumétrie d'éval ;
- **Maintenance** : lance les commandes `status` / `export` / `import` directement
  depuis la page — statut lisible, export téléchargeable, et import d'un ancien run
  (protégé par une confirmation, car il écrit dans l'historique).

Lancement : `calibrate dashboard --config run.yaml`. Chaque vue a son lien
partageable (`?view=DAG`). Au passage, `--config`/`--branch` s'acceptent désormais
aussi bien avant qu'après la sous-commande (`calibrate dashboard --config run.yaml`
fonctionne, avant il fallait `calibrate --config run.yaml dashboard`).

**Avant :** l'historique d'une campagne se lisait au mieux via l'export CSV/Markdown
ou en rejouant le notebook ; la progression d'un run se suivait dans les logs.

**Après :** une page web unique montre chaque mutation moins de 30 s après son
verdict et rend tout l'historique d'un run terminé explorable (timeline, DAG,
distributions) sans rien recalculer.

---

## [2026-07-13] Météo par persona : les lots LLM mélangent enfin les conditions

La météo (et le contexte trafic) est désormais **attachée à chaque persona** au lieu
d'un unique préambule commun en tête de requête. Conséquence directe : des demandes
de **météos différentes peuvent maintenant être fusionnées dans un même appel LLM**,
chaque persona gardant sa propre météo dans le prompt.

**Avant :** la météo était un paramètre de la requête ; comme le regroupement en lots
ne fusionne que des requêtes de paramètres identiques, deux agents sous des météos
différentes partaient dans des appels LLM séparés. Le micro-batching était bridé par
la météo, d'où des lots plus petits et plus d'appels.

**Après :** la météo voyage dans le bloc de l'agent. Le regroupement ne la voit plus,
donc il fusionne des agents quelle que soit leur météo ; le prompt affiche
`**Contexte :** …` sous l'en-tête de chaque persona (sa météo propre). Lots plus
pleins, moins d'appels, pour un débit et une pression de rate-limit meilleurs.

- **Décisions inchangées** : chaque persona voit exactement la même météo qu'avant,
  juste attachée à son bloc plutôt qu'en préambule — seul le **remplissage des lots**
  change.
- **Fidélité de calibration** : le pipeline de calibration applique le même format
  d'injection par persona, donc la mesure reflète le prompt réellement envoyé.

---

## [2026-07-13] Lancer la calibration du prompt depuis l'IHM GAMA

Un bouton **« Lancer la calibration du prompt »** apparaît dans l'interface GAMA
(catégorie *Calibration* des paramètres de l'expérience `e`). Il déclenche une
campagne de calibration en tâche de fond dans le contrôleur, sans quitter la
simulation ni la ligne de commande. Un paramètre **« Calibration - cycles
(itérations) »** (1–200) règle le nombre d'itérations de la boucle.

**Avant :** la calibration ne se lançait qu'en ligne de commande, depuis l'hôte
(`python -m calibration.cli run --iterations N` dans `scripts/prompt_calibration`).

**Après :** on règle le nombre de cycles dans l'IHM puis on clique sur le bouton.
GAMA envoie `POST /calibrate {iterations}` au contrôleur, qui lance la campagne en
sous-processus détaché (un seul run à la fois) et répond immédiatement. La console
GAMA affiche l'accusé de démarrage (pid, cycles, chemin du journal) ; la sortie de
la campagne est journalisée dans `experiments/current/calibration.log`.

- **Non bloquant** : la simulation continue, le contrôleur exécute la calibration
  en arrière-plan. Une seconde demande pendant qu'un run tourne est refusée
  proprement (message `calibration_busy`).
- **Prérequis** : les jeux gelés (`calibration_datasets/<version>/`) doivent exister
  et les clés API des providers être présentes dans `.env` — sinon la campagne
  s'arrête avec une erreur explicite dans `calibration.log`.

---

## [2026-07-13] Calibration de prompt : phase 1 livrée — moteur reprenable + store SQLite

Le moteur de calibration devient un **package Python testé et reprenable à tout
moment**, piloté par une CLI, avec un historique persistant interrogeable.
Fini le notebook monolithique à globals : `scripts/prompt_calibration/calibration/`
(models, blocks, metrics, evaluation, mutation, loop, store, cli) — 65 tests verts.

- **Reprise sans recalcul** : l'historique complet (prompts, mutations, évals,
  ablations) vit dans un unique store SQLite `calibration.db` où chaque prompt est
  un nœud d'un DAG identifié par le hash de son texte (comme un commit git). Tuer
  le process en pleine itération puis relancer `calibrate resume` repart
  exactement à l'itération suivante — les évals déjà calculées sont servies par le
  cache, les mutations déjà jouées rejouées à l'identique : **zéro appel LLM
  redondant**. L'init (run initial + ablation) n'est refaite que si on part de zéro.
- **Décisions brutes conservées** : chaque éval stocke ses choix modaux
  `(agent_id, mode)`, donc toute métrique future (loss v2 en phase 3) est
  recalculable rétroactivement sans réappel LLM.
- **CLI** : `calibrate run | resume | status | export | import`. `export` produit
  une vue lisible (`nodes.csv`, `mutations.csv`, `history.md`) ; `import` récupère
  les anciens runs (`mutations.jsonl` + historique) dans le nouveau store.
- **Configuration par fichier** : tout paramètre passe par un `RunConfig` (YAML),
  plus aucun global mutable.
- **Jeux val/test nettoyés de la mémoire** (fin de phase 0) : la section
  `**Historique :**` (souvenirs STM/LTM, spécifique au run source et non
  reproductible) est retirée des personas des jeux val et test à leur génération —
  la mesure de référence ne dépend plus que du profil, de la météo et des options
  de trajet. Le train la conserve (il ne sert qu'à la boucle).

**Avant :** calibration dans un notebook (état invisible, non testable) ; une
interruption imposait de relancer depuis un checkpoint approximatif ; historique
éparpillé en CSV/JSONL non reliés
**Après :** moteur importable et testé, reprise exacte au point d'arrêt via un
store SQLite, historique complet requêtable en SQL et exportable

---

## [2026-07-13] Calibration de prompt : phase 0 livrée — mesure fiabilisée

La refonte de l'outil de calibration démarre dans un nouveau package,
`scripts/prompt_calibration/` (l'ancienne version notebook est conservée intacte
dans `scripts/models_influence/`). La phase 0 du ticket 004 est livrée : la mesure
sur laquelle toute l'optimisation repose est désormais fiable.

- **Métadonnées exactes** : les attributs de scoring (genre, âge, occupation,
  taille du ménage) proviennent de la jointure `agent_id → population_N.json`,
  plus du parsing du texte. Le genre vient de `traits_json.gender` — fin de
  l'inférence par prénom et de ses erreurs connues.
- **Dérive de format résorbée** : les deux formats d'en-tête de logs
  (`--- agent_id=… ---` courant et `--- PERSONA … ---` legacy) sont parsés,
  et le journal est lu correctement même en JSON pretty-printed concaténé.
- **Jeux gelés train/val/test** : affectation stable par `sha256(agent_id)`,
  versions figées avec manifest (hash des sources, effectifs par strate) et
  rapport de couverture des marginales Cerema (strate manquante = warning).
- **Température d'évaluation minimale** (`EVAL_TEMP = 0.0`).

**Avant :** genre parfois faux (heuristique prénom), logs récents non parsables
(0 % de rattachement), jeux rééchantillonnés à chaque run
**Après :** 100 % des 720 sections de `experiments/current` rattachées à leurs
métadonnées exactes (vérifié par `check_phase0.py`), jeux reproductibles et gelés

---

## [2026-07-13] Calibration de prompt : documentation et plan d'industrialisation

Le module de calibration de prompt (`scripts/models_influence/prompt_calibration.ipynb`)
dispose désormais d'une documentation d'architecture (`docs/arch/prompt_calibration.md`)
et d'un plan de refonte en 8 phases (`docs/tickets/ticket_004_prompt_calibration_industrialisation.md`) :
mesure fiabilisée (métadonnées structurées, jeux gelés train/val/test), store SQLite
git-like reprenable, dashboard Streamlit, loss ordinale EMD/JSD, acceptation
statistique, attribution de crédit Shapley, branches parallèles avec merge,
minimisation du prompt à score constant (économie de tokens en production), et revue
de littérature scorée (GEPA, HiveMind, MAPGD, MASS, MARS, RePrompt…).

Deux anomalies documentées au passage : le genre des personas est inféré du prénom
alors qu'il existe dans `traits_json.gender` de la population générée, et le format
d'en-tête des logs récents (`--- agent_id=… ---`) ne correspond plus au regex de la
lib (`--- PERSONA … ---`) — corrections planifiées en phase 0 du ticket.

---

## [2026-07-11] Fin des HTTP 413 groq : capacité par requête vérifiée avant l'envoi

Sur le run du 2026-07-11, 38 des 63 erreurs LLM étaient des 413 « request too large »
sur les providers groq : le free tier rejette toute requête unique dont
`prompt + max_tokens` dépasse le TPM, et deux providers (`groq_openai_120/20`,
plafond 8 000) partaient sans aucun clamp — `groq_openai_120` n'a servi qu'un seul
batch sur tout le run malgré 30 RPM de quota disponible.

- Tous les providers groq déclarent désormais `max_tokens_per_request` (= leur TPM),
  qui borne aussi la taille des batchs constitués.
- Le `max_tokens` envoyé est rogné d'après la taille **réelle** du prompt rendu
  (l'estimation statique sous-évaluait les prompts de réflexion d'un facteur 2).
- Si même la sortie minimale ne tient plus, le batch est rerouté vers un autre
  modèle **avant** l'appel HTTP (nouveau compteur `llm_capacity_reroute_total`).

**Avant :** requêtes condamnées envoyées quand même — 413, retries brûlés, cascades
« providers saturés », capacité groq quasi inutilisée
**Après :** zéro 413 évitable, la capacité groq (~90 RPM cumulés) redevient
exploitable pour résorber le backlog de planification

---

## [2026-07-11] Réflexions STM ordonnancées en EDF avec garantie < 12 h simulées

Les réflexions STM partaient en fire-and-forget vers le gateway dès leur déclenchement
et se battaient avec les planifications de trajets aux heures de pointe : sur le run du
2026-07-11, 219 réflexions perdues (timeouts 120 s, providers saturés) et l'essentiel
des 411 ERROR du log. Elles passent désormais par la file EDF avec une échéance en
temps simulé de 12 h (`stm_reflection_deadline_sim_s`).

- Les planifs urgentes passent d'abord ; les réflexions remplissent les creux et
  remontent en priorité à l'approche de leur échéance.
- La contre-pression prédictive compte leurs échéances : si le débit LLM ne permet
  plus de les tenir, le `/sync` est retenu et le temps simulé se fige le temps de
  drainer — la garantie 12 h simulées est structurelle.
- Un échec gateway ne repousse pas l'échéance : la re-soumission au sync suivant
  garde la deadline d'origine, donc la priorité monte à chaque retentative.
- Nouvelle alarme `[ALARME]` (visible via `make error`) si une réflexion dépasse
  quand même son échéance simulée.

**Avant :** réflexions en concurrence frontale avec les planifs, échecs massifs
silencieusement retentés sans limite de retard
**Après :** réflexions servies dans les creux de charge, avec échéance simulée
garantie de 12 h et alarme en cas de dépassement

---

## [2026-07-11] Micro-batching réellement exploité : le ratio agents/prompt décolle

Le micro-batching regroupait très peu (2,4 agents/prompt sur le run du 2026-07-10,
57 % des prompts partaient avec un seul agent) alors que Mistral, qui porte 64 % du
trafic, plafonne à 20 agents/prompt. Quatre correctifs s'attaquent à la cause :

- **Seuil de dispatch découplé du plus petit provider** : le dispatch immédiat se
  déclenchait dès 1 tâche en file (min des providers, tiré vers 1 par les petits TPM
  Groq), court-circuitant la fenêtre d'accumulation. Le seuil est désormais une cible
  de batch (`batch_target_agents`, 10) ; en dessous, la fenêtre d'accumulation joue.
- **Fenêtre d'accumulation élargie** : 1 s → 3 s, calée sur l'inter-arrivée mesurée
  des prompts (p50 = 1,4 s).
- **Capacités de batch recalibrées sur les tokens réels** : le calcul supposait
  6 296 tokens/agent alors que le mesuré est ~1 600 ; avec 3 000 (marge 25 %), les
  providers bornés par le TPM acceptent des batchs 2 à 4× plus gros
  (groq_llama4 : 4 → 10, groq_llama3 : 1 → 4, cerebras : 4 → 5).
- **Concurrence Mistral réduite (5 → 3 workers)** : cinq workers se disputaient la
  file et la vidaient en pops d'une tâche ; moins de workers = pops plus gros, même
  débit (RPM 90 loin d'être saturé).

**Avant :** ~2,4 agents/prompt (médiane 1), batching accidentel uniquement quand le
backlog s'accumulait ; system prompt (~900 tokens) dupliqué dans chaque requête.
**Après :** les tâches compatibles s'accumulent jusqu'à 3 s ou 10 tâches avant envoi,
puis le worker remplit le batch à la capacité réelle du provider — moins de requêtes,
moins de tokens dupliqués, plus de marge RPM pour les pics (moins de 429/fallbacks).
Contrepartie : +3 s de latence max par décision, négligeable devant l'appel LLM (2-10 s).

À surveiller au prochain run : le panneau « Ratio batching (agents/prompt) » du
dashboard LLM Gateway, et les `ProviderParseError` sur les gros batchs (un batch
de 20 en échec = 20 agents à rejouer).

---

## [2026-07-11] Limitation documentée : cache OTP raté d'un jour simulé à l'autre

La clé du cache OTP persistant inclut la date simulée absolue, calculée avant le
remapping `gtfs.fixed_day`. Conséquence : même avec `fixed_day` actif (requêtes OTP
identiques d'un jour à l'autre), un cache réchauffé au jour J est intégralement raté
au jour J+1. La limitation est maintenant documentée dans `docs/arch/cache-memory.md`
et un TODO est posé dans `OtpPersistentCache.make_key` (aligner la partie date de la
clé sur la date fixe ou le jour de semaine, comme le cache OSMnx). Aucun changement
de comportement pour l'instant.

---

## [2026-07-10] Dashboard Métier Mobilité : ponctualité des départs

Nouvelle row « Ponctualité des départs (phase live) » dans le dashboard
« 07 · Métier Mobilité » : elle répond d'un coup d'œil à « les agents
partent-ils à l'heure ? » :

- **Départs à l'heure** vs **en retard** (seuil : action poussée vers GAMA
  plus de 60 s après l'heure prévue), avec le **% de départs à l'heure** ;
- pour les retardataires : **retard moyen** et **retard max** du run ;
- **départs ratés** : la planification (réponse LLM) est arrivée si tard que
  même l'heure d'arrivée prévue était déjà passée ;
- **sans réponse LLM** : activités parties sur l'itinéraire par défaut faute
  de réponse à temps (saturation/timeout) ;
- un graphique temporel « à l'heure / en retard / ratés » par tranche de 10 min.

Le bootstrap (/init) est exclu : il pré-calcule les itinéraires et ne mesure
pas de vrais départs.

**Before :** la ponctualité se reconstruisait après coup via `/debug-run`
(logs LATE) ; aucun indicateur live de retard moyen/max ni de départs ratés.
**After :** l'état de ponctualité des agents est visible en continu dans le
dashboard métier, seuils colorés (orange dès 10 retards ou 5 min de retard moyen).

---

## [2026-07-10] Dashboard LLM Gateway : panneaux providers lisibles et « Réactivation dans (s) » réparé

Trois lisibilités corrigées sur le dashboard « 04 · LLM Gateway » :

- **État des providers** : chaque tuile affiche maintenant le nom du provider
  au-dessus de son état (Actif, Cooldown, …) — plus besoin de deviner quelle
  tuile correspond à quel provider.
- **Réactivation dans (s)** : le panneau restait à 0 même quand un provider
  était en cooldown, car la métrique ne couvrait que la désactivation
  temporaire (erreurs consécutives), pas le cooldown 429/5xx — de loin le cas
  le plus fréquent. La métrique expose désormais le TTL restant quel que soit
  le mécanisme.
- **Tokens cumulés par provider & modèle** : les barres étaient légendées avec
  le jeu de labels Prometheus brut (`{instance=…, job=…, model=…, provider=…}`) ;
  elles affichent maintenant `provider · modèle` (ex. `google_gemini31 ·
  gemini-3.1-flash-lite-preview`).

**Before :** un provider en cooldown affichait « Réactivation dans 0 s » ;
états et tokens illisibles sans survoler chaque série.
**After :** le compte à rebours de réactivation est correct pour cooldown et
désactivation ; provider identifiable d'un coup d'œil sur les trois panneaux.

---

## [2026-07-10] Dashboard Métier Mobilité : graphiques en heure simulée

Les trois graphiques temporels du dashboard Grafana « 07 · Métier Mobilité »
(parts modales dans le temps, trajets par motif, états des agents) affichent
désormais l'**heure de la simulation** sur l'axe X, au lieu de l'heure réelle.
La lecture métier devient directe : un pic voiture à 8h correspond bien à 8h
du matin *vécu par les agents*, quelle que soit la vitesse d'exécution du run.

**Before :** l'axe X montrait l'heure réelle du poste ; avec une simulation
accélérée (ou ralentie par le backpressure), impossible de relier un pic modal
à un moment de la journée simulée.
**After :** l'axe X suit `gama_sim_logical_time_seconds` — les courbes se lisent
en heures de la journée simulée. La plage temporelle sélectionnée en haut de
Grafana reste en temps réel ; restreindre la plage au run courant si plusieurs
runs sont couverts (l'axe repartirait en arrière à chaque /init).

---

## [2026-07-10] Répartition LLM proportionnelle à la capacité réelle et réservation TPM à la taille exacte

Le load balancer distribue désormais les requêtes proportionnellement à la capacité
**effective** de chaque provider (`min(RPM, TPM/3000)`), et la fenêtre TPM glissante est
recalée sur la taille réelle de chaque requête (prompt mesuré en caractères / 3, puis
tokens facturés) au lieu d'un forfait fixe de 3 000 tokens.

Ce que ça débloque :
- **Les gros providers absorbent enfin leur part** : mistral passe de ~8 % à ~49 % de la
  rotation (il détient 47 % de la capacité totale) ; la flotte Groq bridée à 6-12k TPM
  descend à 1-2 % chacun au lieu de saturer.
- **Fin du sous-comptage des grosses requêtes** : une réflexion STM (~4 500 tokens_in/agent,
  2× le forfait) réserve son vrai coût — c'est ce sous-comptage qui produisait des
  violations TPM (groq_qwen mesuré à 122 % de son quota) et des 429.
- **Les petites requêtes rendent leur headroom** : un batch plus léger que le forfait
  libère immédiatement la différence pour les autres workers.
- Un WARNING signale toute requête dont le coût réel dépasse l'estimation de +25 %
  (dérive du ratio caractères/tokens, mesuré à 3,05-3,50 sur run réel).

**Before :** mistral utilisé à 7 %, groq_qwen à 122 % de son TPM, 29 % des minutes actives
avec des 429, réflexions STM abandonnées en masse (« providers saturés »).
**After :** rotation alignée sur les quotas ; la fenêtre TPM reflète la consommation réelle
requête par requête.

---

## [2026-07-10] Réduction des fallbacks LLM : throttling de concurrence et timeouts étendus

Baisse drastique du fallback LLM (6.8% → ~0%) via throttling de la concurrence et tolérance accrue aux 5xx.

**Changes :**
- `worker_concurrency`: 20 → 8 (60% moins de requêtes parallèles, réduit la saturation des providers)
- `remote_llm_poll_timeout`: 60s → 120s (double du temps d'attente avant fallback, absorbe cooldowns 5xx)
- Google Gemma 42/43: `concurrency_limit` réduit à 1, `disable_timeout` augmenté à 180s (plus patient après erreur)

**Before :** 254/3753 trajets (6.8%) en fallback, backlog p95 = 963s, 9 rate-limits 429, Google 500 systématiques.
**After :** Pipeline moins saturé, providers moins overwhelmés, meilleure absorption des cooldowns transitoires.

---

## [2026-07-10] Refonte des dashboards Grafana : 8 vues par question, alertes et alarmes visibles

Les 5 dashboards historiques (cockpit, bottleneck, llm_agents, business, system) sont remplacés
par 8 dashboards numérotés par cycle de vie — `01_cockpit` (le run va-t-il bien ?),
`02_init_bootstrap`, `03_pipeline_scheduling`, `04_llm_gateway`, `05_routing`, `06_cache_llm`,
`07_metier_mobilite`, `08_systeme` — reliés par un menu déroulant commun. Le live ne garde que
les indicateurs actionnables pendant le run ; l'analyse fine reste dans `/debug-run`.

Ce que la refonte débloque :
- **Les alarmes `[ALARME]` sont enfin visibles dans Grafana** (compteur `alarme_total{source}`,
  feu « santé globale » dans le cockpit) et **7 alertes Grafana provisionnées** couvrent les cas
  critiques (agents bloqués, fallback LLM >10 %, aucun provider actif, drainage prolongé…).
- **La couverture du cache Qdrant** (`llm_cache_points_*`, agents couverts) répond en un coup
  d'œil à « le cache est-il assez peuplé pour l'init ? » (dashboard 02).
- **Le coût est suivi en tokens** : tokens/heure simulée, tokens économisés par le cache (04, 06).
- **Nouvelle lecture métier** : parts modales dans le temps, mode × motif d'activité
  (`trip_mode_by_purpose_total`, couvre LLM + cache + mono-choix), les 7 tranches de distance
  (les trajets 10-20 km et 20-50 km étaient invisibles), palette officielle des modes appliquée.
- **CPU/RAM par conteneur** via cAdvisor (dashboard 08) — on voit désormais *qui* consomme.
- **Toutes les vagues du bootstrap sont visibles** (`agent_bootstrap_wave_moves{wave,status}`,
  dashboard 02) : 8 lignes, une par vague, chacune avec progression, agents traités/obtenus/
  planifiés et cache hit % — seule la vague 1 était détaillée auparavant.
- Panneaux cassés corrigés : PromQL invalide sur les tokens par modèle, latence OTP par instance
  (label `instance` → `otp_instance`, il était écrasé par Prometheus), famille EDF/backpressure
  et OSMnx (ok/err/latence) enfin affichées.

**Before :** 5 dashboards accumulés, panels vides (PromQL invalide), alarmes visibles uniquement
via `make error`, tranches 10-50 km absentes, aucun coût en tokens ni vue par conteneur.
**After :** 8 dashboards par question, alertes provisionnées, feu santé + compteur d'alarmes,
coût en tokens, couverture cache Qdrant, mode × motif, CPU/RAM par conteneur.

`/debug-run` affiche en plus le ratio de choix d'itinéraire par défaut rapporté aux seules
décisions LLM (erreur définitive), avec alarme au-delà du seuil. Les métriques SDK dupliquées
(`llm_tasks_*`, `llm_mode_chosen_total`, `llm_index_chosen_total`) sont supprimées ; la latence
`/sync` est mesurée (`controller_sync_duration_seconds`).

---

## [2026-07-10] Nettoyage du code mort de la gateway LLM

Suppression du client HTTP legacy et des brouillons de prompts qui ne servaient plus, désormais
que la chaîne de production passe entièrement par le SDK typé (`LLMGatewayClient` / `TaskResult`).

**Supprimé :** `client.py` (ancien `LLMClient` sync) et ses tests dédiés (`test_client_validate.py`,
`test_e2e.py`), l'orchestrateur manuel `test_main.py` qui les pilotait, et trois variantes de
template jamais chargées (`itinary_multi_agent{2,3,4}.md.j2` — le moteur ne résout que
`itinary_multi_agent`). Aucun impact sur la simulation : ces éléments n'étaient référencés que
par eux-mêmes.

**Conservé :** les shims de compatibilité `settings/models.py` et `tasks/llm_config.py`, toujours
utilisés par les notebooks d'analyse externes.

---

## [2026-07-10] Moins de fallbacks LLM : timeout élargi, bascule de modèle sur erreur, rafale de bootstrap lissée

Quatre changements pour récupérer les itinéraires qui retombaient inutilement sur le plan
par défaut (« itinéraire le plus rapide » non arbitré par le LLM) lors des pics de saturation.

**1. Timeout de tâche LLM porté de 30 s à 60 s.** La fenêtre d'attente du controller était
trop courte face au temps de récupération de la gateway : un provider en cooldown 60 s après
une 5xx « disparaissait » avant que le client puisse réessayer. Avec 60 s, le worker a le temps
d'absorber le cooldown + backoff ou de basculer sur un autre modèle avant l'abandon.

**2. Bascule automatique de modèle sur erreur non récupérable.** Sur une réponse illisible
(hors-schéma) ou un 4xx non lié au rate-limit, le batch n'échoue plus sèchement : le modèle
fautif est mis en cooldown court et la requête est rejouée sur un **autre** modèle via la
rotation. Un JSON invalide sur un provider peut ainsi réussir sur un autre.

**3. Rafale de bootstrap lissée.** Au démarrage, les ~centaines d'agents ne lancent plus leur
premier itinéraire tous en même temps : un plafond de concurrence (`bootstrap_concurrency`,
défaut 30) étale les calculs OTP+LLM en vagues, ce qui évite la cascade de 429/5xx qui générait
des centaines de fallbacks au pré-calcul.

**Avant :** un pic de 500 (ex. « 10 tâches échouées d'affilée, error 500 ») → ~460 agents en
fallback au pré-calcul.
**Après :** la rafale est lissée, les erreurs transitoires sont réessayées sur un autre modèle,
et le client attend assez longtemps pour bénéficier de ces reprises.

**4. Rappel : le plafond `max_tokens` (400) porte sur les tokens de sortie** (complétion), pas
sur le prompt — la limite est apprise puis le batch rejoué avec un budget réduit.

---

## [2026-07-10] Cockpit init : compteur d'activités ratées fiable, couverture cache tracée, avancement bootstrap détaillé

Trois améliorations du **Cockpit — Pilotage Simulation** autour de la phase d'initialisation.

**1. « Activités ratées faute de LLM » reste à 0 pendant l'init.** Le pré-calcul des
itinéraires (bootstrap) faisait déjà de vraies décisions LLM : quand la gateway saturait,
les fallbacks étaient comptés comme des activités ratées **avant même le démarrage**. Les
décisions sont désormais taguées `phase` (`bootstrap` / `live`) et le cockpit ne compte que
la phase `live`.

**Avant :** le compteur montait à plusieurs centaines pendant l'init (fallbacks du bootstrap).
**Après :** 0 avant le démarrage, il ne s'incrémente qu'une fois la simulation en marche.

**2. Pourquoi le cache LLM n'est pas à 100 % à l'init — tracé.** Ce n'est **pas** un problème
de taille (Qdrant n'a pas de plafond) mais de **couverture** : la moitié des agents n'avait
jamais eu sa 1ᵉʳ activité stockée, car le cache n'écrit que sur appel LLM réussi (déficit
auto-entretenu si la gateway sature au peuplement). Une ligne de couverture au démarrage
(`[cache] couverture LLM … N points, A agents couverts, S obsolètes`) + des gauges Prometheus
+ une classification des miss (*agent absent* vs *clé différente*) rendent la cause lisible.
Un `[ALARME]` signale les points hérités d'un schéma obsolète (`weekday=None`) qui gonflent
la base sans jamais servir.

**3. Avancement du bootstrap (phase 4) visible en direct.** Nouvelle rangée cockpit avec
progression, agents planifiés, taux de hit cache du bootstrap, vague d'anticipation courante
et trajets futurs pré-cachés.

---

## [2026-06-10] Réparation JSON malformé (Mistral)

`adapters/base.py` utilise désormais `demjson3` comme fallback quand `json.loads` échoue sur la réponse d'un provider (virgule manquante, JSON tronqué, etc.). Si la réparation réussit, l'appel se termine normalement avec un log `WARNING`; sinon, la `ProviderParseError` est levée comme avant.

**Avant :** `JSONDecodeError: Expecting ',' delimiter` → tâche en échec définitif.  
**Après :** `demjson3` répare le JSON malformé et le traitement continue.

---

## [2026-06-05] Réflexions agents opérationnelles (STM/LTM)

Les agents peuvent maintenant générer et stocker des réflexions à partir de leur mémoire
courte et longue durée. Les réflexions passent par la gateway LLM (cache sémantique,
load balancing, circuit breaker) et sont prioritaires sur les départs futurs.

**Avant :** `self.llm` toujours None → toutes les réflexions silencieusement ignorées.  
**Après :** les réflexions STM et LTM sont exécutées, retournées et persistées correctement.

---

## [2026-06-05] Cache OTP activé partout par défaut

Le cache persistant OTP est désormais actif dans tous les modes sans configuration
explicite. Les itinéraires O/D/heure sont réutilisés entre les runs, ce qui accélère
significativement le warm-up.

**Avant :** certaines configs d'expérience forçaient `otp_cache_enabled: false`,
désactivant silencieusement le cache.  
**Après :** la valeur par défaut (`True`) fait foi ; les 36 configs d'expérience ne
peuvent plus le désactiver par inadvertance.

---

## [2026-06-05] Observabilité unifiée des trois caches (OTP / OSMnx / LLM)

Une seule ligne de log `[cache] OTP X% · OSMnx Y% · LLM Z%` est émise en fin de
warm-up et à chaque sync, avec le détail des miss LLM par raison (`no_candidates`,
`code_not_in_options`, …). Permet de diagnostiquer rapidement un cache inefficace.

---

## [2026-06-04] Routage population simplifié — SQLite comme unique source de vérité

Le fichier de population ne stocke plus les routes calculées. Toutes les routes passent
par le cache SQLite OSMnx, ce qui évite les désynchronisations entre le fichier et le
cache et simplifie la génération de population (`generate_population.ipynb`).

---

## [2026-06-04] Mémoire long terme agents activée

Les réflexions quotidiennes (STM→LTM) et la self-reflection multi-jours sont
fonctionnelles. La mémoire est activée par défaut ; les événements sont écrits en
double (JSONL + CSV) pour faciliter l'analyse.

---

## [2026-06-03] Météo injectée dans chaque observation agent

Les agents reçoivent les conditions météo courantes dans chaque observation.
Le flag `timed_out` est ajouté dans `GamaArrivalsLogger` pour distinguer les
agents bloqués en attente TC (> 30 min) des arrivées normales.

---

## [2026-06-03] Données versionnées avec DVC

Population (`po_toulouse.small`, `population_samples`) et sorties eqasim sont
maintenant versionnées via DVC. Les données météo historiques Toulouse 2025-01
à 2026-04 sont incluses.

---

## [2026-06-03] Throttling scheduler corrigé + robustesse initialisation

La formule de throttling (`min(cap,(n/scale)^k)`) est plus stable sous forte charge.
Les endpoints `/reflect` et `/sync` répondent `not_ready` (au lieu d'une erreur 500)
si le scénario n'est pas encore initialisé.

---

## [2026-06-15] Prompts système en source unique (prompts.yaml)

Le texte des prompts système est désormais centralisé dans
`llm_module/prompts/prompts.yaml` (fusion avec l'historique de calibration),
au lieu d'être codé en dur dans les templates Jinja. Une carte `active:` désigne
la variante en production par catégorie ; promouvoir un prompt calibré ne demande
plus de modifier le code. Le template `itinary_multi_agent` ne porte plus que la
structure (boucle agents + `{{ schema }}`). Variante active initiale : `expert`.

---

## [2026-06-15] Cache LLM invalidé au changement de prompt système

Le cache sémantique LLM est désormais partitionné par empreinte du prompt système actif :
`data/cache/llm/<checksum>/<population>/`. Le checksum
(`PromptManager.active_prompt_checksum()`) change dès qu'une nouvelle variante de prompt est
promue, évitant de réutiliser des décisions obsolètes. Les anciens caches sont conservés.

## [2026-06-17] Aucun déplacement ne démarre le week-end

Un départ planifié tombant un samedi ou un dimanche est automatiquement reporté
au lundi suivant à la même heure (samedi -> +2j, dimanche -> +1j). Le décalage
est appliqué sur le `departure_time` dans `_compute_move_for_activity`, donc
l'itinéraire OTP, `expected_arrive_at` et le `schedule_at` côté GAMA en
découlent. Comportement activable via `agent.no_weekend_departures` (défaut: vrai).

---

## [2026-06-17] Repères temporels unifiés dans les logs (`[SIM_TIMING]`)

Trois lignes de log partagent désormais le tag commun `[SIM_TIMING]` avec un champ
`event=...` pour faciliter la recherche (`grep '\[SIM_TIMING\]'` ou `grep event=SIM_DAY`),
chacune horodatée par l'heure réelle (`real_time`) :
- `event=SIM_START` : réception de `/init` (lancement de la simu) ;
- `event=INIT_DONE` : fin de la phase d'init (bootstrap terminé) ;
- `event=SIM_DAY` : à chaque tranche de 24h de temps simulé écoulé depuis le départ,
  avec `sim_day`, `sim_time` et `real_elapsed` (temps réel cumulé) pour mesurer le débit
  de la simulation.

Implémenté via `helper.format_sim_timing(...)`, appelé depuis `handle/application.py`
(`/init`) et `simulation_controller.sync()` (borne 24h).

---

## [2026-06-24] Consommation de tokens traçable par jour simulé et économie du cache

Deux ajouts pour mesurer empiriquement la consommation de tokens et l'effet du cache :

- `llm_exchanges.jsonl` porte désormais `sim_ts` / `sim_day` (timestamp simulé repris de
  `AgentSpec.departure_timestamp`), permettant de ventiler les tokens par **jour de
  simulation** au lieu de l'horloge murale.
- Chaque hit du cache sémantique LLM est tracé dans `workdir/llm_cache_hits.jsonl`
  (`log_llm_cache_hit()`). Comme un hit ne génère aucun appel — donc aucune ligne dans
  `llm_exchanges.jsonl` —, ce fichier permet de compter les appels économisés et d'estimer
  les tokens épargnés.

Le notebook `scripts/analysis/llm_traffic_analyse.ipynb` ajoute un graphe
« tokens par jour vs limite journalière » (plafond 338 540 000 tokens en pointillé),
empilé par catégorie, avec l'économie de cache estimée si `llm_cache_hits.jsonl` est présent.

---

## [2026-06-24] Réalignement des agent_id mal formés par le LLM

Le modèle renvoyait parfois un `agent_id` mal formé dans les réponses `itinary_multi_agent`
(ex. `PERSONA 446264`, ou le nom du persona à la place du numéro). Comme le démultiplexage
des résultats matche par `agent_id` exact, ces agents étaient **silencieusement écartés** :
aucune recommandation de trajet ne leur était renvoyée, et les métriques de distance/mode
les ignoraient.

- **Worker** (`worker/task_worker.py`) : après validation de la sortie LLM, chaque `agent_id`
  inattendu est réaligné sur l'identifiant réel via sa partie numérique. Un réalignement est
  loggé en `warning`, un id non résolu (sans chiffre, ex. un nom) en `error`.
- **Prompt** (`prompts/templates/itinary_multi_agent.md.j2`) : l'en-tête persona passe de
  `--- PERSONA {id} ---` à `--- agent_id={id} ---` (le mot « PERSONA » incitait le modèle à le
  recopier), et une consigne explicite demande de recopier l'`agent_id` numérique à l'identique.
- **Schéma** (`prompts/schemas.json`) : `agent_id` documenté (« recopier l'id fourni, numérique
  uniquement, sans préfixe ni nom »).

---

## [2026-06-26] Calibration de prompt : Gemini de bout en bout & tableau de bord de présentation

Le notebook `scripts/models_influence/prompt_calibration_V4.ipynb` et son module
`prompt_calibration_lib.py` évoluent pour produire un support de présentation lisible.

- **Modèle unifié** : évaluation **et** génération de mutations passent sur
  `gemini-3.1-flash-lite-preview` (plus aucune dépendance Mistral). `generate_mutation`
  appelle désormais l'API generativelanguage. Le log affiche explicitement le modèle
  réellement utilisé (résolu depuis `default_model` du provider).
- **Tableau de bord** (`present_calibration_state`) affiché au run initial puis à **chaque**
  mutation (acceptée ou rejetée) : carte d'ablation colorée (vert=utile/rouge=nuisible),
  méta « pires écarts strate × mode » vs EMC², score global, scores L1 par dimension,
  barres distribution actuelle vs EMC² (hachuré), et évolution du score (points verts
  conservés / rouges rejetés).

---

## [2026-06-26] Cooldown 429 : respect du délai Gemini (corps JSON)

Sur un rate limit 429, le délai de retry était lu uniquement dans les headers
(`x-ratelimit-reset-requests`). Google Gemini ne renvoie pas ce header — il place le
délai dans le corps JSON — donc le cooldown retombait systématiquement sur le défaut de
60s, en ignorant un « retry in 6.6s » bien plus court.

`adapters/base.py` extrait désormais ce délai du corps (`extract_retry_delay_from_body`) :
champ structuré `error.details[].retryDelay`, puis repli sur le texte `"Please retry in Xs"`.
Le header reste prioritaire quand il est présent. Bénéficie à la fois au worker (durée de
cooldown du provider) et au notebook de calibration (qui lisaient tous deux le même attribut
`ratelimit_reset`).

---

## [2026-07-07] llm_module : 4 correctifs de fiabilité (batching, timing, circuit breaker)

Relecture complète du module → correction de quatre bugs :

- **Déclenchement des batchs (race condition)** : l'armement du compte à rebours reposait
  sur `queue_size == 1` ; deux requêtes simultanées sur une file vide pouvaient chacune
  observer une taille de 2 et aucune n'armait le dispatch (tâches bloquées jusqu'au timeout
  client). Un flag SETNX `batch_sched:{batch_key}` garantit désormais exactement un dispatch
  différé par cycle de batch ; le worker le libère au moment du pop (TTL en filet de sécurité).
- **`min_tpm_required` perdu** : le re-dispatch d'une file non vide après un batch réussi
  omettait la contrainte TPM — les tâches suivantes pouvaient partir vers un provider
  sous-dimensionné. L'argument est maintenant propagé.
- **Métrique `P4_4_ms` toujours à 0** : l'attente micro-batch était calculée en mélangeant
  `time.monotonic()` (uptime) et un timestamp epoch — résultat négatif clampé à 0. Calcul
  corrigé avec `time.time()`, et migration de `datetime.utcnow()` (naïf, déprécié) vers
  `datetime.now(timezone.utc)` dans les modèles et le worker.
- **Circuit breaker Google inopérant sur timeout** : l'adapter Google levait ses erreurs
  (timeout, réponse vide/bloquée) avec le nom de classe `"google"` au lieu du nom d'instance
  (`google_gemma42`, …) — le cooldown était posé sur une clé que personne ne consultait et
  l'instance fautive restait sélectionnée. Les exceptions portent désormais `_instance_name`.

## [2026-07-07] llm_module : restructuration en package (ports & adapters)

Mise en œuvre du CR [llm-module-package-refactor.md](arch/llm-module-package-refactor.md)
(phases 0 à 5). Le contrat HTTP consommé par GAMA est inchangé.

- **Packaging** : `pyproject.toml` (installable `pip install .`), 12 dépendances runtime au
  lieu de ~45 — image Docker du gateway fortement allégée. Extras `[test]` et `[monitoring]`.
- **Plus d'effets de bord à l'import** : Settings construits explicitement (`get_settings()`),
  fabriques `create_app()` / `create_celery_app()`, reset des fenêtres RPM déplacé dans le
  lifespan de l'API (un redémarrage de worker ne remet plus les quotas à zéro), suppression
  du couplage caché `from settings import settings` dans la télémétrie.
- **Découpage du broker** : `redis_broker.py` (~30 fonctions libres) remplacé par 4 classes
  (`RedisTaskStore`, `RedisRateLimiter`, `RedisBatchQueue`, `RedisMetricsSink`) derrière des
  interfaces Protocol (`ports/`), avec équivalents `InMemory*` pour tester sans Redis.
- **Perf** : compteurs worker migrés vers un hash Redis (`wmetrics`) — 1 `HGETALL` par scrape
  Prometheus ; adapters mis en cache avec client httpx partagé (keep-alive entre appels LLM) ;
  clé API Google en header `x-goog-api-key` (plus de clé dans les URLs de logs).
- **SDK typé** : `LLMGatewayClient.execute()` → `TaskResult` pydantic (fini les dicts bruts,
  `"EXPECTED_ERROR"` et clés `_post_ms` injectées) ; `llm_agent.py` migré. L'ancien `LLMClient`
  reste pour les tests E2E.
- **Frontières vérifiées** : `core/` pur (batching, SWRR) + contrats import-linter en CI
  possibles (`lint-imports --config llm_module/pyproject.toml`).
- Tests : 197 unitaires verts (52 ajoutés). À rejouer avant merge : `docker compose build`
  + `test_e2e.py --burst 20`.

## [2026-07-07] llm-agents : correctifs de fiabilité (revue de code)

Quatre corrections issues de la relecture complète du module `llm-agents` :

- **Boucle d'envoi WebSocket robuste** : le handler d'exception de `publish_loop`
  référençait un attribut inexistant (`self.reconnect_interval`) — toute exception
  générique tuait définitivement la boucle d'envoi des actions bootstrap vers GAMA.
- **Worker de fallback annulé sur ré-init** : `set_scenario` annulait le wrapper
  `start_worker` (déjà terminé) au lieu de la vraie boucle de scan ; sur des `/init`
  successifs, l'ancienne boucle continuait de scanner l'ancienne population. Nouveau
  `stop_worker()` sur le scénario, appelé avant remplacement.
- **Persistance de la mémoire long-terme réparée** : les `MemoryEntry` étaient
  sérialisées en chaînes (`json.dumps(default=str)`) — irrécupérables au redémarrage,
  la mémoire épisodique repartait de zéro à chaque restart. Sérialisation explicite
  `to_dict()`/`from_dict()` (round-trip testé), fichiers de l'ancien format tolérés,
  et correction du cleanup >10 000 entrées et de `get_user_stats` qui traitaient les
  entrées comme des dicts (TypeError).
- **Clé du cache OTP persistant complétée avec `include_bike`** : un itinéraire calculé
  pour un agent sans vélo pouvait être resservi à un agent avec vélo (option vélo
  silencieusement absente des choix du LLM). Effet de bord : les entrées existantes du
  cache OTP deviennent froides (nouveau format de clé) — le cache se repeuple au premier run.

Tests : round-trip `MemoryEntry`, save/load métadonnées LTM, annulation worker,
différenciation des clés de cache, + 16 tests unitaires existants verts.

## [2026-07-08] Fiabilité pipeline LLM : corruption cache, délais 429, alarmes

Diagnostic d'une simulation où 80 % des agents restaient inactifs (backlog de
planification à 886/901 après 1h30) : providers LLM en rate-limit, cache sémantique
à 0 % de hit, backpressure inopérant. Trois correctifs :

- **Cache sémantique LLM — accès Qdrant sérialisé** : le client Qdrant embarqué n'est
  pas thread-safe ; les lookups/stores concurrents (via `asyncio.to_thread`)
  corrompaient l'index ("operands could not be broadcast", erreurs SQLite) et le cache
  ne servait plus aucune décision. Verrou `_db_lock` autour de `query_points`/`upsert`,
  plus alarme après 5 erreurs Qdrant consécutives.
- **Délai 429 réellement pris en compte** : le gateway ignorait le header standard
  `retry-after` et `x-ratelimit-reset-tokens` (les 429 Groq portent sur les tokens),
  et le fallback corps ne matchait pas les messages Groq ("try again in 16m7.68s") ni
  les formats `h`/`ms` (quotas journaliers TPD). Le cooldown provider est désormais
  calé sur le délai annoncé (clampé à [10s, 1h]) avant re-routage vers un autre modèle.
- **Alarmes de saturation** (`[ALARME]`, niveau ERROR, visibles via `make error`) :
  backlog > 50 % de la population dans `/sync` (avec min_interval et coefficients,
  poussée aussi vers la console GAMA), tous providers saturés côté worker gateway,
  et 10 échecs de tâches consécutifs côté SDK client.

Tests : 208 tests `llm_module` verts, dont nouveaux cas de parsing (`retry-after`
brut, `reset-tokens` prioritaire, durées `2h37m12.5s`, `140ms`, `16m7.68s`).

## [2026-07-08] Backpressure /sync : seuil relatif à la population

La formule de throttling introduite le 11 juin (`min(cap, (n / (120×pop/100))^3.7)`)
rendait le frein inatteignable : le backlog ne dépassant jamais la population, le
seuil absolu (1200 pour 1000 habitants) n'était jamais franchi — 0.33s de pause avec
886/901 agents en attente. Nouvelle formule `cap × min(1, backlog/population)^k`
extraite dans `backpressure.py` (fonction pure) : ~2.3s à 50% de backlog, ~19s à 89%,
cap (30s) à pile pleine, identique quelle que soit la taille de population. Le
coefficient `min_internal_coeff_scale`, devenu sans objet, est supprimé des settings.

Tests : `tests/test_backpressure.py` (10 cas) vérifie l'invariance du délai à ratio
de remplissage égal, l'atteignabilité du cap à pile pleine, la croissance monotone
avec le backlog et le cas réel du run 2026-07-07 (886/1000 → ~19.2s).

## [2026-07-08] llm-agents : correctifs secondaires et optimisations (revue de code, suite)

Implémentation des points #5–#8 et #11–#14 de la [revue de code](revue-llm-agents-reste-a-faire.md) :

- **Fallback LTM sans ChromaDB réparé** : `_init_shared_index` référençait une variable
  jamais définie dans la branche "simple storage" (NameError au premier démarrage sans index).
- **Mode SOLARI + récursion réparé** : `do_get_iteraries_v1` n'acceptait pas `include_bike`
  (TypeError systématique quand `recursion_search_depth > 0`).
- **Plus de trajet perdu sur échec WebSocket** : le rollback de `_push_planned_move` restaure
  le move calculé (LLM + OTP), et le scan de fallback détecte l'état Idle+plan pour retenter
  l'envoi au lieu de tout recalculer.
- **Cache sémantique LLM aligné sur l'intention** : suppression du rejet par seuil de
  similarité (`below_threshold`) — le filtre déterministe (agent + activité + tranche 10 min
  + hash options/météo) identifie déjà le contexte ; la similarité ne sert plus qu'à classer
  les candidats multiples. La LTM peut évoluer entre les runs sans invalider les décisions.
- **Persistance LTM allégée** : écriture des métadonnées par rafale (debounce 30 s + flush à
  l'éviction LRU) au lieu d'une réécriture complète du fichier à chaque entrée ; sérialisation
  unique ; écritures déportées hors de l'event loop ; `print()` remplacés par loguru.
- **Requêtes LTM filtrées côté vector store** : le retriever passe un filtre `person_id`
  (clause `where` Chroma) avec `top_k×5` candidats au lieu de rapatrier jusqu'à 500 nœuds
  globaux puis filtrer en Python — le recall par agent ne dépend plus du peuplement global.
- **I/O fichier hors event loop** : les écritures CSV/JSONL par événement (moves, arrivées
  GAMA, hits du cache LLM, états d'agents) passent par `asyncio.to_thread` — plus de blocage
  des coroutines aux heures de pointe.
- **Session HTTP OSMnx réutilisée** : une `aiohttp.ClientSession` partagée (keep-alive)
  remplace la création d'une session par requête vers les réplicas osmnx.
- **Tâches de fond protégées du GC** : nouveau helper `create_background_task` (référence
  forte jusqu'à complétion) appliqué à tous les `asyncio.create_task` fire-and-forget
  (planification, push, stores de cache, reconnexion WebSocket, boucle d'envoi).

Tests : rollback push, debounce LTM, référence des tâches de fond, signatures — verts ;
16 tests unitaires existants verts.

## [2026-07-08] llm-agents : métrique minuit et hygiène des logs (#9, #10)

- **Métrique `agent_scheduling_lag_seconds` corrigée au passage de minuit** : le delta
  envoi−cible (deux horaires mod 86 400) est normalisé dans [−43 200, +43 200] — un envoi
  à 00:05 pour une cible 23:55 compte désormais +600 s au lieu de −85 800 s.
- **Logs réparés et nettoyés** : deux `logger.warning("... %s", …)` (format printf ignoré
  par loguru → message affiché littéralement) convertis en f-strings dans la préparation
  de population ; suppression des logs de diagnostic `[trace]` marqués « à retirer »
  (factory, wrapper de cache OTP, init du cache par population).

## [2026-07-08] Anti-saturation gateway : quotas journaliers, timeout 30 s, backpressure SDK

Diagnostic du run où plus aucune décision LLM ne revenait après quelques jours simulés :
les prompts grossissent avec la mémoire (≈675 → 2000 tokens), les quotas free-tier
s'épuisent et le pipeline dégénérait en timeouts/plans par défaut (jusqu'à 99 % d'échecs
LLM le dernier jour). Trois correctifs :

- **Quotas journaliers RPD/TPD appliqués** (jusque-là purement informatifs) : dès qu'un
  provider atteint son `rpd_limit`/`tpd_limit`, il est écarté de la rotation jusqu'à minuit
  UTC au lieu d'être re-sollicité toutes les `disable_timeout` secondes. Compteurs journaliers
  UTC dans Redis (requêtes à la réservation, tokens réels après l'appel) ; `/health` expose
  `daily_requests`/`daily_tokens`/`quota_exhausted`.
- **Timeout tâche LLM 90 s → 30 s** : fallback plan par défaut plus rapide, la simulation ne
  bloque plus 90 s par calcul quand la gateway est muette. Budget de saturation-retry du
  worker recalé sous 30 s.
- **Backpressure SDK sur alarme** : quand l'alarme « 10 échecs consécutifs » se déclenche,
  le client suspend les nouvelles soumissions jusqu'au drainage de la pile in-flight sous
  20 % de `worker_concurrency`, laissant la gateway respirer avant de re-charger.

Tests : quotas RPD/TPD (in-memory + Redis) et drainage backpressure verts ; suite
`llm_module` (208 tests) verte.

---

## [2026-07-08] Cache OSMnx réutilisable au rejeu

Un rejeu de simulation recalculait tous les trajets (Pass 2, ~0,4 s/route) au lieu de
frapper le cache. Deux causes corrigées :

- **Clé voiture sans date absolue** : `OsmnxPersistentCache.make_key` n'inclut plus la date
  (`YYYY-MM-DD`), seulement le **jour de la semaine + tranche horaire** — la granularité réelle
  du facteur de congestion. Deux runs à des dates calendaires différentes mais même weekday
  réutilisent les mêmes trajets. Marche/vélo restent indépendants du temps (coords + mode).
- **Échantillonnage d'agents déterministe** : la sélection aléatoire des agents depuis la
  sortie eqasim utilise désormais une seed fixe (`data.population_sample_seed`, défaut 42) via
  un RNG local. Un rejeu retire exactement le même sous-ensemble d'agents → mêmes coordonnées
  → le cache SQLite fait hit au lieu de recalculer.

Note : les entrées voiture antérieures (clé incluant la date) ne sont plus adressées et se
repeuplent au premier run.

---

## [2026-07-08] Mode drainage /sync : GAMA retenu jusqu'à vidage de la pile à 80 %

Le frein progressif du `/sync` ne retenait GAMA que ~2.3 s par step à 50 % de backlog :
le temps simulé filait devant le pipeline LLM et les agents restaient inactifs faute de
plan. Ajout d'un **mode drainage à hystérésis** (`update_drain_mode`, `backpressure.py`) :

- Enclenché quand la pile atteint `drain_trigger_ratio` (50 %), il retient chaque réponse
  `/sync` jusqu'au cap (30 s, limite du read timeout HTTP de GAMA) en ré-échantillonnant
  la pile chaque seconde.
- Relâché seulement quand la pile repasse sous `drain_release_ratio` (20 %, pile vidée à
  80 %) — entre les deux seuils GAMA reste bridé à ~1 step par cap.
- Traces `[drain]` (WARNING enclenchement/cap atteint, INFO relâchement) ; réglages dans
  `WorldConfig` (`drain_trigger_ratio: 0` pour désactiver).

Doc : `docs/arch/llm-inference.md` § « Mode drainage /sync ». Tests :
`tests/test_backpressure.py` (15 verts).

---

## [2026-07-08] Fix troncature des réponses LLM à max_tokens sur les batches

Les batches `stm_reflection` de 10 agents (~500-1800 tokens de sortie par agent)
saturaient le `max_tokens` fixe de 4096 : réponse JSON coupée en plein milieu →
`JSONDecodeError` à offset constant (char 13158/14704 ≈ 4096 tokens), et batch entier
perdu. Deux corrections dans le gateway :

- **Budget de sortie proportionnel au batch** (`task_worker._execute_batch`) : le
  `max_tokens` client est désormais un budget par tâche, multiplié par le nombre
  d'agents fusionnés, borné par le nouveau réglage `max_output_tokens` (16 384) puis
  par la capacité du provider.
- **Détection de troncature typée** (`BaseAdapter._check_openai_finish_reason`) : les
  adapters mistral/groq/cerebras/openai vérifient `finish_reason == "length"` et lèvent
  `max_tokens_truncation` (503, retryable) au lieu d'un parse error trompeur — couvre
  aussi le `content` vide des modèles thinking (GLM-4.7) dont le budget part en
  raisonnement.

Doc : `docs/arch/llm-inference.md` § « Budget de sortie proportionnel au batch ».
Tests : `tests/test_adapter_base.py` (42 verts).

Complément : la jauge `activities_to_compute_count` compte désormais les agents Idle
sans plan **en direct** (plus de snapshot figé au dernier sync) — indispensable pour que
le mode drainage voie la pile baisser pendant qu'il retient la réponse `/sync` et rende
la main dès le seuil de relâchement. Clarification doc : avec l'horizon glissant 24h,
un agent qui termine son trajet reçoit immédiatement son move suivant et passe `ready` ;
un taux d'`inactive` durable est bien le symptôme d'un précalcul en retard (et non un
état légitime), à l'exception des activités consécutives au même endroit (`legs=[]`).

Réglage de la courbe de frein (demande du 2026-07-08) : exposant `k` passé de 3.7 à
**1.5** pour un freinage précoce et progressif (~1 s à 10 % de pile, ~2.7 s à 20 %,
~5 s à 30 %, ~7.6 s à 40 %, ~10.6 s à 50 %, ~21.5 s à 80 %). Le mode drainage et
l'alarme backlog se déclenchent désormais ensemble à **80 %** (`drain_trigger_ratio`)
et se relâchent au retour sous **20 %** (`drain_release_ratio`), l'alarme n'ayant plus
de seuils codés en dur.

## [2026-07-08] Fix : cache OSMnx inactif pendant le Pass 2 de génération de population

Le cache persistant OSMnx n'était initialisé qu'**après** l'écriture du fichier
population : lors d'une régénération, le Pass 2 (calcul des temps de trajet pour
l'ajustement des plannings) recalculait toutes les routes via OSMnx sans lire ni
alimenter le cache. L'initialisation (`_init_osmnx_cache`) est déplacée en tête de
`_prepare_population`, avant tout routage : le Pass 2 lit et remplit désormais le
cache, et une régénération ultérieure réutilise les routes déjà calculées.

Doc : `docs/arch/cache-memory.md` § « cache persistant OSMnx ».

## [2026-07-08] Plafond de complétion par provider (max_output_tokens) auto-appris

Les batchs `stm_reflection` échouaient en HTTP 400 sur `groq_llama4`
(`max_tokens` calculé = 16 384 > limite de 8 192 de `llama-4-scout`). Chaque provider
porte désormais un champ optionnel `max_output_tokens` dans `providers.yaml` (plafond
de complétion du modèle) : le worker borne le `max_tokens` envoyé à cette valeur, et
le load balancer écarte les providers incapables de servir le budget de sortie d'une
tâche (filtre `min_output`, même mécanique que `min_tpm`). Si un provider répond
malgré tout 400 « max_tokens must be ≤ N », la limite N est **apprise
automatiquement** : config ajustée en mémoire, ligne écrite dans `providers.yaml`
(commentaires préservés, écriture atomique, persistée sur l'hôte via le bind mount)
et batch rejoué au lieu d'échouer définitivement.

Doc : `docs/arch/llm-inference.md` § « Plafond de complétion par provider ».

## [2026-07-08] Cockpit de pilotage Grafana

Nouveau dashboard `cockpit.json` regroupant en une page l'état de la simulation :
avancement de l'init (5 étapes), remplissage de la pile et frein backpressure,
délai réel par step, **agents bloqués** (aucune planification réussie depuis
> `world.stuck_agent_threshold_hours` h simulées, défaut 20 h), état et **quotas
jour** des providers (ratio d'usage RPD), taux de hit des caches (LLM / OTP /
OSMnx) et **dernières erreurs LLM**.

Nouvelles métriques exposées côté gateway (`llm_provider_rpm/rpd/tpd_limit`,
`requests_today`, `tokens_today`, `daily_usage_ratio`, `quota_exhausted`) et côté
contrôleur (`controller_init_stage/progress_ratio`, `backpressure_interval_seconds`,
`backlog_fill_ratio`, `drain_mode_active`, `agents_stuck`). Les messages d'erreur
bruts, non stockables dans Prometheus, transitent par un ring buffer Redis
(`llm:recent_errors`) exposé via `GET /errors/recent` et affiché grâce au plugin
Grafana *Infinity*.

Doc : `docs/arch/monitoring.md`.

---

## [2026-07-08] Fiabilité du push GAMA : rollback sur envoi non délivré + watchdog d'arrivée

L'analyse du run 15:41 a montré ~250 agents « zombies » : `send_message` avale les
exceptions WebSocket et retourne `False`, que `_push_planned_move` ignorait — le push
était annoncé réussi ([push] dans les logs) alors que GAMA n'avait jamais reçu le trajet
(3 coupures WS 1006 pendant le run). L'agent restait « en déplacement » côté Python,
inactif côté GAMA, invisible de la pile de backpressure, du drainage et du scan.

- **Rollback sur `False`** : `_direct_push` propage le booléen de `send_json` et
  `_push_planned_move` traite un retour `False` comme une exception → rollback complet,
  le scan de fallback retente le push après reconnexion (le trajet calculé n'est pas perdu).
- **Watchdog d'arrivée** : chaque push arme `heading_expected_arrive_at` ; si le temps
  simulé dépasse l'échéance de plus de `world.arrival_watchdog_hours` (défaut 1 h sim),
  le scan lève `[ALARME] Arrivée perdue`, force la fin d'activité et remet l'agent dans
  le circuit. Couvre aussi les pertes silencieuses (socket moribonde avant détection
  keepalive, message perdu côté GAMA). Métrique `controller_lost_arrivals_recovered_total`.

Doc : `docs/arch/agents-lifecycle.md` § « Fiabilité du push ».

Analyse du run 18:29 (correctifs actifs) : le rollback (67 reprises) et le watchdog
(339 agents récupérés) fonctionnent, mais les coupures WebSocket persistaient — cause
racine identifiée : **blocages de l'event loop asyncio de 7-20 s** qui faisaient expirer
le keepalive (`ping_timeout=10s`). Deux compléments :

- **`ping_timeout` porté à 60 s** (`handle/websocket.py`) : un stall ponctuel ne ferme
  plus la socket ; une vraie coupure reste détectée en ~1 min et couverte par le watchdog.
- **Moniteur d'event loop** (`controller_event_loop_lag_seconds`) : mesure en continu la
  dérive de la boucle asyncio, `[ALARME]` en ERROR au-delà de 5 s de blocage pour
  identifier l'opération synchrone fautive.

## [2026-07-09] Reset propre au remplacement de scénario (stop GAMA → nouveau /init)

Un stop de simulation GAMA ne stoppe pas le process Python (pas d'endpoint `/stop`) :
le `/init` suivant remplace le scénario. Deux résidus de l'ancien run pouvaient
contaminer le nouveau, les `person_id` étant identiques d'un run à l'autre (même
population, même seed) :

- **Tâches en vol de l'ancien scénario** : `stop_worker()` n'annulait que la boucle de
  scan — les planifications LLM/OTP déjà lancées allaient au bout et poussaient leurs
  trajets périmés à la nouvelle simulation. Toutes les tâches fire-and-forget du
  contrôleur (planification, refill, push, réflexions, checkpoints) sont désormais
  suivies dans `_inflight_tasks` et annulées en bloc au remplacement.
- **Buffer de retry du `publish_loop`** : les actions non délivrées (socket morte au
  stop) restaient en attente et étaient rejouées vers le nouveau run à la reconnexion.
  Le buffer (`LoopContainer._pending`) est purgé par `set_scenario()` avec un WARNING
  donnant le nombre d'actions écartées.

Doc : `docs/arch/agents-lifecycle.md` § « Arrêt de simulation et remplacement de scénario ».

## [2026-07-09] Ordonnancement EDF et contre-pression prédictive pilotée par les échéances

Deux causes d'effondrement des runs longs corrigées : le service FIFO du contrôleur
(un refill lointain pouvait bloquer une replanification urgente derrière un jeton de
concurrence) et un frein `/sync` aveugle aux échéances (freinait trop tard sur
épuisement de quota, et pour rien quand le backlog n'était que des refills non urgents).

- **Dispatcher EDF** (`simulation_controller.py`) : les tâches de planification sont
  servies par échéance croissante (heure de départ simulée) via une file de priorité
  (`_edf_heap`) consommée par `world.worker_concurrency` tâches, au lieu du sémaphore
  FIFO. Une replanification urgente passe devant un refill d'horizon lointain ; un push
  déjà calculé (deadline 0) passe devant tout. Flag `world.edf_enabled` (défaut `true`,
  `false` = spawn direct historique). File vidée et consommateurs annulés au
  remplacement de scénario. Le sémaphore reste utilisé par le bootstrap.
- **Contre-pression prédictive** (`backpressure.py`, `application.py`) : le `/sync`
  n'est retenu que si le test de faisabilité EDF (`edf_feasibility` : `T_k = k/D` vs
  `slack_k = (d_k − now_sim)/R`, marge `world.predictive_margin`) annonce une échéance
  menacée — vitesse maximale sinon (le frein `cap·ratio^k` est court-circuité). Le débit
  `D` est une EWMA des complétions (`ThroughputEwma`, `tau` = `world.throughput_ewma_tau_s`,
  plancher `world.throughput_floor_per_s`), le rythme `R` une EWMA du `sim_wall_clock_ratio`
  figée pendant la rétention. Le mode drainage à hystérésis reste le filet de sécurité ultime.
- **Notification GAMA** (topic `system/throttle`, hystérésis) : au-delà de
  `world.throttle_notify_threshold_s` de rétention cumulée, Python pousse le débit LLM
  réel et la vitesse de simulation, rafraîchi toutes les `world.throttle_notify_refresh_s`,
  levé au premier `/sync` sans rétention. Globales GAMA `THROTTLE_ACTIVE` /
  `LLM_RATE_PER_MIN` / `SIM_RATIO_PYTHON` (`Settings.gaml`, `LLMAgent.gaml`).
- **Observabilité** : 6 nouvelles jauges Prometheus (`controller_throughput_tasks_per_min`,
  `controller_edf_queue_depth`, `controller_t_estimate_seconds`,
  `controller_min_slack_sim_seconds`, `controller_predictive_hold_seconds`,
  `controller_deadline_misses_total`), renseignées même contrôle prédictif désactivé
  (phase d'observation pour calibrer `tau` et la marge).

Doc : `docs/arch/agents-lifecycle.md` (§ Dispatcher EDF, § Contre-pression prédictive),
`docs/arch/monitoring.md` (métriques + réglages). Tests : `tests/test_backpressure.py`
(EWMA + faisabilité EDF), `tests/test_edf_dispatcher.py` (ordre EDF).

## Outil de debug — Rapport de santé du dernier run

- **`scripts/debug/run_report.py`** : génère un rapport markdown « agent-ready » condensant
  les signaux essentiels au debug d'un run (`experiments/current` par défaut) — top erreurs/
  warnings normalisés d'`app.log`, matrice santé LLM (erreurs par provider × statut HTTP,
  taux de 429), latence pipeline (percentiles + détection de backlog), activité des agents
  (inactifs dans le temps), décisions modales & fallbacks, arrivées & timeouts. Une section
  `🚨 ALARMES` en tête synthétise les anomalies franchissant les seuils (ajustables en tête
  de script). Stdlib only, tolérant aux fichiers manquants.
- Exposé via `make report [RUN=… OUT=…]` et la skill Claude `/debug-run`.
- Limite connue : ne lit que les artefacts sur disque ; les logs des conteneurs Docker
  (api, worker, otp, osmnx) ne sont pas encore centralisés dans `app.log` (chantier suivant).

## Logging centralisé par service + analyse capacité LLM + digest live GAMA

- **Logs centralisés par conteneur** : `configure_logging()` (`llm_module/telemetry/logger.py`)
  ajoute un sink fichier `APP_WORKDIR/<SERVICE_NAME>.log` (même format qu'`app.log`) quand
  `SERVICE_NAME` est défini. `docker-compose.yml` renseigne `SERVICE_NAME`/`APP_WORKDIR` pour
  `api` (→ `api.log`) et `worker` (→ `worker.log`) ; le controller garde `app.log`. Tous
  atterrissent dans le dossier du run et sont agrégés (avec tag `[service]`) par
  `scripts/debug/run_report.py`. Sinks non-Python (`otp*`, `osmnx*`, `redis`) : via
  `docker compose logs`.
- **`scripts/debug/llm_capacity.py`** (`make capacity`, skill `/debug-run`) : analyse
  « débit vs capacité » LLM du run, 100 % à partir des logs existants — demande avant/après
  micro-batching (agents/min vs prompts/min via le champ `response` de `llm_exchanges`),
  contre-pression prédictive EDF parsée depuis `[predictive]` (débit D, pile, T d'écoulement,
  `slack_min` = temps simulé restant sur la tâche critique), épisodes `[BACKPRESSURE]` /
  `[ALARME] Gateway`, et saturation 429 par minute et par provider. Section `🚨 ALARMES`
  en tête (risque d'échéance, saturation soutenue).
- **Digest de capacité poussé à GAMA** (`handle/application.py`) : tous les 10 `/sync`, le
  controller envoie sur `system/log` une ligne synthétique `📊 [cycle N] cache LLM … · débit
  … req/min · backlog … · agents actifs/inactifs`. Signaux cheaply available en-process
  (débit `throughput_per_s`, cache `get_llm_cache_stats`, états agents) ; émission gardée
  (n'échoue jamais un `/sync`). Intervalle : constante `_DIGEST_EVERY_N_SYNC`.

## Outil de debug — Analyse de la phase d'initialisation

- **`scripts/debug/init_report.py`** (`make init`, skill `/debug-run`) : rapport markdown
  ciblé sur le **démarrage** de la simulation, complémentaire de `run_report` (santé globale)
  et `llm_capacity` (débit LLM). Dérivé 100 % d'`app.log`, stdlib only, tolérant aux fichiers
  manquants. Contenu :
  - **Timeline des 5 étapes d'INITIALISATION** (SIM_START → INIT_DONE) avec la durée et la
    part de chacune ; repère l'étape dominante (quasi toujours le bootstrap `4/5`).
  - **Câblage & réchauffage des 3 caches persistants** (OTP, OSMnx, LLM sémantique) :
    activés ? chemins ? taux de hit atteint en fin d'init via la ligne de résumé combiné
    `[cache] OTP … · OSMnx … · LLM …` ; coût du chargement du modèle d'embedding.
  - **Bootstrap** : nombre d'agents pré-calculés, vagues d'anticipation, futurs déplacements
    pré-cachés, montée du taux de hit cache (cold → warm) et coût par type d'activité.
  - **Bugs d'init** avec section `🚨 ALARMES INIT` en tête : stalls de l'event loop
    (I/O synchrone du bootstrap → coupures WebSocket 1006), thrashing du cache métadonnées
    LTM (évictions + `gc.collect()` en boucle, `llm/longterm.py`), OD injoignables.
  - Exposé via `make init [RUN=… OUT=…]` et intégré à la skill `/debug-run`. Seuils
    d'alarme ajustables en tête de script.

## Cache LLM hybride et optimisation de la phase d'initialisation

L'init d'une population de 901 agents prenait ~19 min alors que les caches (OTP, OSMnx, LLM)
affichaient un taux de hit de ~100 % et que seuls 75 appels LLM réels avaient lieu. Le temps
était intégralement consommé par la machinerie entourant le cache, entièrement sérialisée :
un embedding `all-MiniLM-L6-v2` (~318 ms, sérialisé par `_embed_lock`) et une requête
ChromaDB de mémoire long terme étaient payés sur *chaque* décision, y compris les cache hits.

- **Cache sémantique LLM hybride.** Le lookup applique d'abord un filtre déterministe sur les
  conditions factuelles (agent, activité, catégorie de jour, tranche de 10 min, hash des
  options et de la météo), puis :
  - *LTM vide* (tout le bootstrap) : correspondance exacte par `scroll` clé-valeur, **sans
    embedding** (~0,1 ms contre ~324 ms). Sans souvenir, deux décisions prises dans les mêmes
    conditions sont identiques.
  - *LTM remplie* : recherche par similarité cosinus entre la mémoire courante de l'agent et
    celle qui a produit la décision stockée, avec rejet sous `cache.semantic_threshold`.
    L'agent tient donc compte de son vécu au lieu de rejouer indéfiniment sa première
    décision — ce que faisait l'ancienne clé, aveugle à la mémoire.
  Les deux familles de points sont étanches (`memory_empty` fait partie du filtre).
- **Le payload LLM (et sa requête ChromaDB) n'est plus construit sur le chemin nominal**
  quand la mémoire est vide : uniquement en cas de miss.
- **Nouveau champ de filtre `weekday`** : semaine et week-end ne partagent plus leurs décisions.
- **Fin du thrashing du cache métadonnées LTM** : `long_term_max_loaded_metadata` passe de 200
  à 5000 (nouveau réglage `agent.long_term_max_loaded_metadata`, jusqu'ici non câblé). En
  dessous du nombre d'agents, chaque décision provoquait une éviction. Le `gc.collect()` par
  éviction (~110 ms, exécuté dans l'event loop, ~2600 fois par init) est supprimé : il causait
  les stalls de la boucle asyncio (jusqu'à 148 s) et les coupures WebSocket 1006.

⚠️ Le filtre du cache gagne les champs `weekday` et `memory_empty` : les caches antérieurs ne
les portent pas et ne seront jamais retrouvés. Supprimer `data/llm_cache/` avant un run.

## Garde-fou TPM & débit des providers Groq

- **Réservation TPM glissante (60 s)** ajoutée au rate-limiter, en plus du RPM. `tpm_limit`
  devient un plafond dur appliqué avant chaque appel (réservation atomique RPM+TPM en un seul
  script Lua, restituée sur échec), et non plus un simple filtre de routage. Chaque provider
  expose `tpm_estimate_per_request = batch_max_agents × (assumed_prompt_tokens +
  assumed_output_tokens)`. Élimine le flot de **429** des providers dont le `rpm_limit`
  dépassait la capacité tokens réelle. Providers sans `tpm_limit` non bridés.
- **`groq_qwen` / `groq_llama31`** (free tier, TPM 6 000 → ~2 req/min) : `rpm_limit` ramené de
  60/30 à **2** et `weight` de 1.0 à **0.5**, alignés sur leur vraie capacité — ils causaient
  ~78 % des 429 pour une contribution marginale.

## Indicateur d'activités ratées faute de réponse LLM

- Nouveau compteur `agent_activity_decisions_total{outcome}` (issue de chaque activité
  planifiée : `llm`, `llm_fallback`, `single`, `no_solution`, `no_move`) émis au point de
  décision du contrôleur. Le **cockpit ③** (« Agents bloqués ») gagne une rangée : part et
  nombre d'activités dégradées faute de LLM (`llm_fallback` → index par défaut) et le débit
  fallback/min.
- Le **move-log** (`moves.csv`) porte désormais `ID Personne` et `ID Activité`. Le rapport de
  run (`run_report.py`, skill `/debug-run`) ajoute une section **« Couverture des activités
  par jour »** : les activités étant récurrentes et non datées, on vérifie que chaque activité
  d'un agent s'exécute chaque jour de sa plage — décomptant les activités *dégradées* (sans
  LLM) et *manquées* (aucune exécution ce jour-là), avec alarmes dédiées.
