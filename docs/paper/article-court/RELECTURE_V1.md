# Relecture v1 des sections rédigées — corrections à appliquer

Version anglaise : [`RELECTURE_V1.en.md`](RELECTURE_V1.en.md), rendu fidèle de ce fichier, qui reste la référence.

Relecture du 2026-09-22 des huit fichiers de `sections/`, faite en relecteur AAMAS sans
accès à l'historique. **Hypothèse : le ticket 103 rend son scénario 1** et les quatre
placeholders `[c2]` des § 5.1 et § 5.3 se remplissent avec ses scores. Rien ici ne porte sur
ces quatre trous ; tout le reste est à faire, dans l'ordre du § 9.

Note d'ensemble en l'état : **13/20**, contre 7/20 pour la version longue. Les deux reproches
du tuteur sont levés. Ce qui reste est du fond à corriger localement et de la finition.

Chaque point porte : le passage, la correction, le coût en mots, le test. Le rédacteur
applique, met à jour le commentaire `<!-- source: -->` concerné, et rend le bloc de
compte-rendu de la règle 20.

---

## 1. Corrections globales

**G1 — Séparateurs de milliers.** 65 nombres portent l'espace fine française (*1 000*,
*3 299*, *39 203*) contre 13 la virgule anglaise (*11,329*). Convention : virgule partout
(*1,000*, *3,299*, *39,203*), y compris dans les tableaux et l'abstract.
*Test :* `grep -c "[0-9] [0-9]\{3\}\b" sections/*.md` rend 0.

**G2 — Bloc de compte-rendu manquant.** Aucun des huit fichiers ne porte le
`=== SECTION REPORT ===` de la règle 20. Les signalements de l'agent ne sont que dans les
commentaires HTML, un à un. Ajouter le bloc en fin de chaque fichier, en commentaire HTML,
rempli pour l'état courant.
*Test :* `grep -l "SECTION REPORT" sections/0*.md` rend les huit fichiers.

**G3 — Le tic de remplacement.** Le deux-points a disparu ; la phrase en deux propositions
coordonnées par « , and » avec une chute courte l'a remplacé. *« …and no further. »*,
*« …and not a day longer. »*, *« …and it stops being taken. »*, *« …and this paper supplies
them. »*, *« …and the language model intervenes only there. »* Sur cinq pages, c'est un
rythme de maxime. En casser une sur trois : subordonnée, deux phrases, ou reformulation.
*Test heuristique :* `grep -c ", and [a-z ]\{3,30\}\.$" sections/*.md` baisse d'un tiers.

**G4 — Compiler et compter les pages.** 5,930 mots de prose (+14 % sur 5,200), cinq figures,
quatre tableaux. Personne n'a compilé. Le tenu en 8 pages est la contrainte qui décide de
toutes les coupes du § 8 ; le mesurer avant de polir.
*Test :* le PDF fait 8 pages au plus, références exclues, aucun `??`.

**G5 — La résolution de ±1.3 est périmée.** § 4.3 : *« That estimate predates the correction
of the scoring set. »* Ce chiffre sert de règle dans tout le § 5 (« 1.5 to 5.5 times the
cohort resolution », « 0.56 against ±1.3 »). Le recalculer sur le jeu corrigé par le
rééchantillonnage par grappe existant (script du ticket 096 lot 2, 2,000 réplicats), puis
remplacer la valeur et supprimer la phrase de réserve. C'est une heure de machine.
*Test :* le mot *predates* a disparu du § 4.3 ; la nouvelle valeur apparaît aux § 4.3, 5.1, 5.2.

---

## 2. § 0 — Abstract

**A1.** *« Verbalised deliberation earned its place outside that ordinary day. »* Le passé
fait lire un événement, pas un résultat. → *« Verbalised deliberation earns its place outside
that ordinary day. »*

**A2.** Quand le § 5.3 est rempli : *« matches them for a fiftieth of the cost »* prend le
statut mesuré hors échantillon, sans chiffre si le budget de 300 mots ne le permet pas
(*« matches them on a second cohort, for a fiftieth of the cost »*).

**A3.** G1 s'applique : *1,000*, *3,299*, *21*.

---

## 3. § 1 — Introduction

**I1 — La plateforme et la filiation, absentes.** Ni GAMA, ni la lignée du dispositif. Ajouter
en fin de § 1.3, avant le paragraphe des contributions :
*« The agents live in a GAMA simulation of the Toulouse area, with its real networks and
timetables, in the line of the GAMA–OpenTripPlanner–LLM architecture of Vu et al. (2025). »*
(+25 mots.) La citation `vu2025modeling` est déjà dans le `.bib`.

**I2 — Définition en double.** *« a decision-maker being anything that turns a trip
description into a probability over the options offered »* est au § 1.3 **et** en tête du § 4,
mot pour mot (règle 8). Garder celle du § 1.3, reformulée en proposition pleine :
*« We call decision-maker anything that turns a trip description into a probability over the
options offered. »* Supprimer celle du § 4 (−20 mots).

---

## 4. § 2 — Travaux liés

**R1 — Une seule référence comportementale, et c'est une auto-citation.** Le § 2.1 tient
« des écarts que l'enquête n'enregistre pas » sur Adam & Gaudou 2025 seul, co-auteur du
papier. Ajouter deux références sur l'habitude et l'inertie dans le choix modal — candidats à
vérifier : Gärling & Axhausen 2003 (*Transportation*, numéro sur l'habitude), Verplanken et al.
1997 (habitude et choix modal). Une phrase, +25 mots, deux entrées `.bib` à créer.

**R2 — CitySim et MATSim ont disparu.** CitySim est le seul autre système LLM à l'échelle
d'une ville ; c'est exactement le vide que le papier comble. Rétablir au § 2.2, après Liu et
al. : *« CitySim (Bougie & Watanabe, 2025) scales such agents to a city and validates them on
time use, but no experiment confronts a simulated modal split with an observed one. Earlier
simulators such as MATSim (Horni et al., 2016) reach equilibrium by scoring plans, and the
agent does not deliberate. »* (+50 mots.) Les deux clés existent dans le `.bib`.

**R3 — Le débat sur le raisonnement écrit n'est pas cité.** § 2.3, dernier paragraphe :
*« The gains reported for written reasoning come from tasks that have one verifiable
answer. »* C'est la phrase qui protège le § 5.3 de « connu », et elle n'a pas de source.
Citer Wei et al. 2022 (chain-of-thought prompting) et un travail sur les conditions où le
raisonnement écrit aide (Sprague et al. 2024, *To CoT or not to CoT*). Deux entrées `.bib` à
créer, +10 mots.

**R4 — Nommer GAMA chez Alves.** *« They couple a multi-agent platform to a language-model
module »* → *« They couple the GAMA platform to… »*. L'anonymat n'est pas une raison : une
plateforme ne désanonymise pas.

---

## 5. § 3 — L'agent

**T1 — La plateforme, nommée et décrite (+110 mots).** Le § 3.1 dit *« A multi-agent
platform carries the world »* et *« the routing engines »*. Sans les noms et sans ce qu'ils
apportent, un relecteur MAS demande où est le système multi-agents, et le § 6 perd son sol :
la panne est un fait de simulation, pas un texte injecté. Réécrire le premier paragraphe :

> *Three components carry the simulation. A GAMA multi-agent simulation carries the world:
> the real geography of the 453 communes, the transport networks, the clock, and the physical
> execution of every trip. OpenTripPlanner produces the public transport itineraries on the
> real timetables; a shortest-path computation on the OpenStreetMap graph produces the direct
> trips by foot, bicycle and car. A controller carries the agent lifecycle, builds the options
> available at the departure hour, and holds the clock so that no agent leaves before it has
> decided. A decision module produces the choice, and the language model intervenes only
> there.*

Le deux-points après « the world » est le seul du paragraphe (R2). Le paragraphe suivant
(*« The loop closes… »*) reste.

**T2 — Le saut dans le foyer, une phrase au § 3.3.** Le mécanisme est décrit au § 6.2 puis
déclaré non exercé. Sa place de conception est ici : *« In the evening each household member
tells the others their day, and that account enters the hearers' reflection. »* (+20 mots.)
Puis N1 raccourcit le § 6.2 d'autant.

---

## 6. § 4 — Le banc

**Q1 — Supprimer la définition en double** (voir I2). −20 mots.

**Q2 — L'affirmation de diffusion de la cohorte n'est pas tranchée.** *« We release the
protocol, the code, the seeds and the synthetic cohort itself. The status of the other
resources derived from the survey is not settled. »* La cohorte vient d'eqasim, qui lit
l'enquête ; son statut est celui des « autres ressources dérivées »
(`SOUMISSION_AAMAS_2027.md` l. 81). Personne n'a pris cet engagement. →
*« We release the protocol, the code and the seeds. Whether the synthetic cohort, derived from
the survey through the synthesis chain, can be released is not settled. »*
*Test :* les mots *cohort itself* ont disparu.

**Q3 — Après G5**, remplacer la valeur de résolution et retirer *« That estimate predates the
correction of the scoring set. »*

**Q4 — Tableau 1, quand le lot B du ticket 103 a rendu :** remplacer les deux
*[replay pending]* par les étendues mesurées ; les *not replayed* restent. La mention
*(in sample)* sur la ligne Jev expert reste, puisque c'est un score c1 ; ajouter sous le
tableau : *« The out-of-sample measurement of that row is in Section 5.3. »*

---

## 7. § 5 — Résultats

**F1 — § 5.1, après le lot B :** remplir *[c2, inter-seed range per key decision-maker]* ;
réécrire les deux phrases *« The minimal-prompt condition has not been replayed… The effect of
the seed on the sign of the paired differences reported here is therefore not measured »*
selon Q3 du ticket : soit « no published difference changes sign across seeds », soit la
liste de celles qui changent, qui sortent alors du texte.

**F2 — § 5.2, la strate des 15–19 ans en annexe F (−40 mots).** Trois phrases qui
n'alimentent aucune des quatre affirmations du § 5. Garder : *« One stratum resists every
decision-maker, the 15–19 year olds (Appendix F). »*

**F3 — § 5.3, après le lot A :** remplir les trois placeholders. **La phrase de conclusion du
deuxième paragraphe se choisit après lecture de Q2** : si `prompt_expert_32` améliore gemini
autant que Jev, écrire que l'effet est dans le texte ; s'il n'améliore que Jev, écrire que
l'effet est dans le couple. Ne pas écrire la phrase avant les scores.

**F4 — § 5.4, tableau 3 : deux Jev sous une seule étiquette.** La ligne *Typed classifier*
à 64.3 % est le bras à **consigne transférée** (`prompt_expert_05`, annexe I.1 bis « Jev,
consigne gemini-3.5 »). Le § 5.3 parle du classifieur sous **sa propre consigne réglée**,
qui fait 64.7 % dans la même annexe. Le lecteur croit lire le même décideur. Mettre les deux
lignes, étiquetées *Typed classifier, transferred instruction* (64.3) et *Typed classifier,
own instruction* (64.7 ; entropie croisée 0.464 ; rappels vélo et marche à prendre dans
l'annexe I.2). Les deux sont sous le plancher, l'affirmation en sort renforcée. Le texte qui
suit (*« It reaches 64.3 % where the floor reaches 66.7 % »*) nomme alors le bras. +15 mots.

**F5 — § 5.4, le 93.4 % déclaré non recalculé.** *« a figure carried from the earlier
manuscript and never recomputed independently »* : honnête, et non publiable. Retrouver le
`metrics.json` de la variante (celle dont la distance était reconstruite depuis la durée
déclarée) et recalculer `accuracy_weighted`. Si la source n'est pas retrouvée en deux heures,
le paragraphe sort en entier (−90 mots) et la leçon de mesure passe au § 7.2 en une phrase
sans chiffre.

**F6 — § 5.4, vérifier le 8.3.** *« The median distance between two agent distributions is
four times the distance between two tabular ones, 39.0 points against 8.3. »* Le 39.0 est à
l'annexe H.5 (ligne expert gemini-3.5 / gradient boosté). Le 8.3 doit être dans la même table,
sur une paire tabulaire nommée ; sinon la phrase sort.

---

## 8. § 6 — Le régime non tabulé

**N1 — Le saut dans le foyer, raccourci (−40 mots).** Le § 6.2 le décrit en quatre phrases
puis dit *« The single-agent case below does not exercise this step. »* Après T2, deux
phrases suffisent : le mécanisme existe, il n'est pas exercé ici.

**N2 — Numéroter le tableau des fréquences** : *« Table 4 — Car taken when the car is
offered… »*, pour la cohérence avec les trois autres. C'est un quatrième tableau : si G4 rend
plus de 8 pages, il redevient une phrase (*« 94 %, 32 % then 88 % of the trips where the car
was offered, against 90, 92 and 87 % for the control »*).

**N3 — § 6.1, une redite.** *« No comparator can be run against this result, and none could
be. »* répète la phrase précédente. Supprimer (−12 mots).

---

## 9. § 7 — Implications

**P1 — Qui note la gravité.** § 6.2 dit que dans le cas tracé *« that severity came declared
with the incident »* ; § 7.1 écrit *« The language model receives what no variable carries,
rates it, and writes it into memory. »* Le § 7.1 crédite le modèle d'un geste que le § 6 dit
non exercé. → *« The language model receives what no variable carries and writes it into
memory; rating its severity is its task in the current design, and the traced case did not
exercise it (Section 6.2). »*

**P2 — § 7.2, après le lot B :** *« one agent, one event and one seed »* reste vrai pour le
§ 6 ; ajouter une phrase sur ce que les trois graines du § 5 couvrent et ne couvrent pas.

---

## 9 bis. Ce que le texte raconte de lui-même, et qui n'intéresse personne

Deux familles de phrases ont passé la relecture précédente et la règle 14 de l'agent ne les
nommait pas. **L'histoire du papier** : ce qu'on a trouvé, corrigé, recalculé, ce qui a été
fait dans quel ordre. **La justification d'implémentation** : pourquoi le dispositif est fait
comme ça, quand la réponse ne change rien à ce que le lecteur doit comprendre. La charte
`article-verrou` les interdit toutes deux (règle de fond 3 : la fabrication plutôt que la
mesure). Un relecteur y lit soit une confession, soit un procès-verbal de développement.

Le tri ci-dessous garde ce qui répond à une objection réelle (le lecteur *va* demander
pourquoi la voiture reste offerte après une panne) et retire ce qui ne répond qu'à l'auteur.

### Histoire du papier — à retirer

| § | Passage | Correction | Mots |
|---|---|---|---:|
| 4.3 | *That estimate predates the correction of the scoring set.* | Déjà G5/Q3 : recalculer, puis retirer la phrase. | −10 |
| 4.4 | *The typed classifier's instruction was tuned differently, and it required a second cohort. Its mutations read the classifier's gaps on the cohort that scores it, so its score there is in sample. We therefore measure every published crossing…* | Quatre phrases de procès-verbal. → *The classifier's instruction was tuned on the first cohort; every crossing of models and instructions is therefore measured on a second cohort, which shares no persona with the first.* La réserve « in sample » reste dans l'étiquette de la ligne du tableau 1. | −35 |
| 4.4, légende T1 | *The typed classifier's expert prompt was tuned on the cohort that scores it.* | Redite de l'étiquette *(in sample)* de la ligne. Retirer. | −12 |
| 5.2 | *The expert text was tuned against gemini-3.5 on a calibration population drawn apart from the scored cohort. Its score here is therefore out of sample for that model.* | Déjà dit au § 4.4 (*tuned against one language model on a separate calibration population*). Garder au § 4.4, retirer ici. | −25 |
| 5.4 | *One earlier variant shows what a decision-maker scored in the wrong place looks like. Scored on the survey it reached 93.4 % accuracy, a figure carried from the earlier manuscript and never recomputed independently. In simulation it produced the worst composite of that campaign, 9.28 against 7.40 for the published condition, on the reading that keeps every decision. Excluding single-option trips the two values become 11.31 and 10.07, so the ordering holds and the margin falls from 1.88 to 1.24 points.* | Tout le paragraphe est le journal de débogage : « earlier variant », « that campaign », « the published condition », « carried from », et un contrôle de robustesse sur deux lectures. La leçon est un résultat, pas un aveu. → *A variant whose distance input had been reconstructed from the declared travel time reached 93.4 % accuracy on the survey and the worst composite in simulation, 9.28 against 7.40: the reconstructed distance carried the mode. We therefore score a decision-maker where it is used, not where scoring is convenient.* Conditionné à F5 (le 93.4 recalculé). | −60 |
| 6.2 | *…and rating it is the language model's task in the current design.* | « in the current design » est du dispositif, pas du résultat. → *In the run below, the severity was declared with the incident rather than rated by the model.* | −5 |
| 6.3 | *Both runs keep memory enabled, where every measurement of the bench ran with memory disabled.* | Le § 3.3 dit déjà que le banc tourne mémoire éteinte. → *Both runs keep memory enabled.* | −10 |
| 5.1 | *The minimal-prompt condition has not been replayed under those seeds. The effect of the seed on the sign of the paired differences reported here is therefore not measured.* | État d'avancement, pas résultat. Disparaît avec F1 ; si une graine manque encore à la soumission, une phrase au § 7.2 et rien au § 5. | (F1) |

### Justification d'implémentation — à retirer ou réduire

| § | Passage | Correction | Mots |
|---|---|---|---:|
| 5.3 | *The cheaper decision-maker sends the larger input. The typed classifier sends 1 050 input tokens per decision against 629 for the language model, its instruction being resent whole at every call. The gap comes from the tariff rather than from the volume, at 0.042 dollar per million input tokens with the output not billed.* | Pourquoi le moins cher envoie plus de tokens, le cache, le tarif : personne ne lit un papier pour ça. → *At an equal load of 23,026 decisions the classifier costs 1.06 dollar against 49.28, a factor of about fifty.* Le détail tokens/tarif va en annexe I. | −45 |
| 4.4 | *We estimate the four at strict parity, on one file with one split.* | « one file » ne veut rien dire pour le lecteur. → *estimated on the same survey partition.* | −5 |
| 4.4 → 5.3 → 0 → 7.3 | *under a fixed output type, writing nothing* / *under a fixed output type, and it produces no sentence* / *reads the same context under a fixed output type, and writes no text* / *reads the same context and writes nothing* | Le classifieur typé est défini quatre fois. Une définition au § 4.4 ; ensuite *the typed classifier*. L'abstract garde la sienne, c'est un texte autonome. | −25 |
| 5.1 + 5.3 | *We report this as an observation on two versions of one model family, not as a property of language models in general.* / *We state that as a result on this bench, not as a property of language models.* | Deux fois la même défense. Garder celle du § 5.3, où elle porte ; au § 5.1, *on two versions of one model family* en incise et rien d'autre. | −15 |
| 2.3 | *…and we claim no agreement with its results on games.* | Défense contre une objection que personne n'a formulée (le § 2.3 dit déjà que SILICA mesure des jeux). Retirer la proposition. | −10 |
| 6.3 | *The car remains offered the next morning, the condition for measuring an arbitration rather than a constraint. A real engine failure would immobilise the vehicle; this one does not.* | La première phrase répond à une vraie objection : garder, compressée. La seconde est la limite : une fois, au § 7.2. → *The car remains offered the next morning, so that what we measure is an arbitration and not a constraint.* | −15 |
| 7.1 | *We give no share of trips per stage either, since no counter of ours separates an ordinary decision from a disrupted one.* | « no counter of ours » est une excuse d'outillage. → *We do not estimate the share of trips each stage would take.* | −10 |

### Ce qui reste, et pourquoi

- § 3.2 *The options are listed in a random order, so that rank does not become preference* :
  un contrôle contre un biais publié (SILICA), une proposition. Reste.
- § 4.2 *Ranking alone would send every persona of one profile into the same mode* : la
  raison de la règle 2, que le lecteur doit avoir. Reste.
- § 4.3 *Trips of one person are not independent, so every interval comes from resampling
  clusters at the person level* : méthode, pas justification. Reste.
- § 4.4 la phrase sur les mutations du prompt expert : c'est la reproductibilité, une phrase.
  Reste.

**Total de cette section : −282 mots.** Il paie les +255 de la plateforme (§ 10).

---

## 10. Budget et ordre des coupes

| Ajouts | | Coupes | |
|---|---:|---|---:|
| T1 plateforme | +110 | Q1 définition en double | −20 |
| R2 CitySim, MATSim | +50 | F2 strate 15–19 | −40 |
| I1 filiation | +25 | N1 foyer au § 6.2 | −40 |
| R1 références habitude | +25 | N3 redite § 6.1 | −12 |
| T2 foyer au § 3.3 | +20 | Q2 diffusion | −10 |
| F4 ligne Jev | +15 | | |
| R3 CoT | +10 | § 9 bis, histoire du papier | −157 |
| | | § 9 bis, justification d'implémentation | −125 |
| **Total** | **+255** | | **−404** |

Solde **−149 mots → environ 5,780 de prose, +11 % sur le budget**, dans la marge de 15 %. C'est
G4 qui tranche quand même. Si le PDF dépasse 8 pages, couper dans cet ordre, en s'arrêtant dès
que ça tient :

1. § 5.2 : les sept valeurs de part voiture par tranche deviennent « rises by six to seven
   points in every band between one and fifty kilometres » (−35).
2. § 6.4 : le tableau 4 redevient une phrase (N2) (−30 et un float).
3. § 4.3 : le paragraphe sur les deux lectures d'accompagnement passe en une phrase (−40).
4. § 5.1 : le paragraphe « The backbone model weighs as much as the instruction » perd sa
   seconde phrase (−20).
5. § 5.4 : F5, si le 93.4 n'est pas recalculé (−90).

---

## 11. Ordre d'exécution

1. **G1** — mécanique, cinq minutes, avant tout pour ne pas relire deux fois.
2. **Q2, F4, F5, P1, N3** — les corrections de fond locales. Une heure.
2 bis. **§ 9 bis** — retirer l'histoire du papier et les justifications d'implémentation.
   Avant la plateforme : ce sont ces coupes qui la paient.
3. **T1, T2, I1, R2, R4** — la plateforme. Ce sont les seuls ajouts qui changent la lecture
   d'un relecteur MAS.
4. **Q1, F2, N1** — les coupes qui paient.
5. **G5** puis **Q3** — la résolution recalculée.
6. **R1, R3** — deux `.bib` à créer, quatre entrées.
7. **G3** — le tic, en relecture d'ensemble.
8. **Quand le ticket 103 rend : F1, F3, Q4, A2, P2.**
9. **G2** — les blocs de compte-rendu, sur l'état final de chaque section.
10. **G4** — compiler, compter, appliquer les coupes du § 10 si besoin.
11. Puis seulement la passe française.
