# Ticket 078 — Ce qu'un membre du foyer apprend, personne d'autre ne l'apprend

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-15. Mécanisme arrêté par l'auteur le jour même (§ 11).
>
> **Objet.** Un agent consolide seul, apprend seul, et meurt avec ce qu'il a appris. Le foyer
> existe pourtant dans les données depuis le sceau — `household.id` — et il est **le seul groupe
> social de la simulation qui porte un identifiant stable**. Ce ticket en fait un canal : à la
> **consolidation journalière**, ce que les autres membres du foyer ont appris depuis la dernière
> fois entre dans l'appel **comme une entrée de plus**, aux côtés des expériences personnelles de
> la journée.
>
> **Pas de passe séparée, pas de prompt dédié, pas un seul appel LLM supplémentaire.** La
> consolidation journalière devient : *expériences personnelles de la journée* **+** *ce que le
> foyer a raconté*. C'est la seule addition.
>
> **Dépendance stricte : le [077](ticket_077_la_memoire_apprend_sur_des_observations_fausses.md)
> livré en entier**, lots A et B compris (§ 8) — sans le lot A le filtre de partage est vide de
> sens, sans le lot B le partage propagerait à tout le foyer des marches qui n'ont pas eu lieu.
>
> **Contrat de test.** `specs/ticket_078/tests.md`, écrit AVANT le code, comme les lots du 071 et
> du 077.
>
> **Drapeau.** `agent.memoire__partage_foyer_enabled`, **faux par défaut**, surchargeable depuis
> GAMA comme les autres drapeaux de mémoire. Tout ce qui a été mesuré avant ce ticket reste
> comparable, et le bras « sans partage » est un interrupteur, pas une reconstruction.

---

## 0. Ce que la cohorte contient déjà, et que personne n'utilise

Mesuré sur `data/population/toulouse_population_1000_AAMAS_v6.json`, le 2026-09-15 :

| Constat | Mesure |
|---|---|
| Ménages distincts représentés | **499** |
| Agents sans `household.id` | **0** |
| Ménages dont **un seul** membre est présent | 212 |
| Ménages dont **plusieurs** membres sont présents | **287** |
| Agents vivant avec au moins un autre agent de la simulation | **788 sur 1 000** |
| Tailles présentes | 2 → 158 · 3 → 65 · 4 → 46 · 5 → 16 · 6 → 1 · 7 → 1 |

Le tirage par ménage du [ticket 029](ticket_029_selection_par_menage_marges_multiples.md) a fait
entrer les foyers **entiers** : ce n'est pas un hasard d'échantillonnage, c'est une propriété de la
cohorte scellée. Quatre agents sur cinq ont donc, dans la simulation, quelqu'un avec qui parler le
soir — et aujourd'hui rien ne passe.

**Et ces gens-là ne se ressemblent pas.** Sur les 287 ménages multi-membres :

| Attribut où les membres diffèrent | Ménages concernés |
|---|---|
| Motifs de déplacement | **223** |
| Occupation | 206 |
| Permis de conduire | **133** |
| Abonnement de transport collectif | 122 |
| Vélo personnel | 120 |

C'est l'argument central. Si tous les membres d'un foyer vivaient la même journée, le partage
n'apporterait qu'une redondance de plus — et le [077](ticket_077_la_memoire_apprend_sur_des_observations_fausses.md)
vient de montrer ce que coûte la redondance. Ici, le foyer 5177 met sous le même toit **Constance
Ledoux, 12 ans, sans permis et sans vélo, qui ne fait que des trajets d'études**, et **Jacques
Aubert, 49 ans, permis, vélo personnel, qui ne fait que du travail**. Ce que Jacques apprend du
réseau, Constance ne peut pas l'apprendre seule ; et ce qu'il apprend de la voiture ne doit
**jamais** devenir une croyance de Constance.

Le foyer est déjà un objet de modélisation dans le dépôt — l'habitat et la taille de ménage
([019](ticket_019_habitat_taille_menage.md)), le tirage par ménage ([029](ticket_029_selection_par_menage_marges_multiples.md)),
la voiture partagée en attente ([018](ticket_018_partage_voiture_foyer.md)). Il n'a jamais été un
**canal**.

---

## 1. Ce qui se partage — et ce qui ne se partage jamais

**Seuls les concepts passent.** Les entrées épisodiques (`CONVERSATION`, `EVENT`, `REFLECTION`)
restent strictement personnelles.

La raison n'est pas d'économie, elle est de définition. Un épisode dit *ce qui m'est arrivé* : le
recopier chez un autre agent lui fabrique un souvenir faux, c'est-à-dire exactement le défaut que
le 077 est en train de réparer. Un concept dit *ce qui est vrai du monde* — « le 401 est
généralement à l'heure », « l'abri à vélos sature à 8 h 30 » — et c'est précisément ce qui se dit
à table. La séparation épisodique / sémantique de Tulving (1972), déjà portée par l'architecture
(`est_episodique`, § « Consolidation des concepts » de `docs/arch/memory-stm-ltm.md`), sert ici de
frontière de transmission : elle existe, il suffit de s'en servir.

---

## 2. Quand — à la consolidation journalière, et nulle part ailleurs

Le partage n'a **pas** de moment à lui. Il se greffe sur l'appel qui a déjà lieu :

| Heure simulée | Ce qui se passe | Origine |
|---|---|---|
| 22 h | Plancher journalier : tout agent au tampon non vide devient éligible à la consolidation | [048](ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) |
| 22 h → réveils | Drainage nocturne des réflexions, en file EDF, par ordre de réveil | [071](ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md) |
| **à chaque consolidation** | **le bloc « ce soir à la maison » est construit et joint à l'appel** | **ce ticket** |
| 3 h | Point de reprise du jour — il emporte le repère de lecture du § 3 | [075](ticket_075_journal_de_memoire_et_run_60_jours.md) |

**Aucun ordre n'est exigé entre les membres, et c'est délibéré.** Faire attendre B que A ait
consolidé introduirait une barrière dans une file EDF dimensionnée pour ne pas en avoir — et un
foyer de sept suffirait à la bloquer. Le repère de lecture du § 3 rend l'ordre indifférent : ce
que A produit après le passage de B n'est pas perdu, il est lu par B **la nuit suivante**. Le
partage est donc *au fil de l'eau*, avec un décalage d'au plus une nuit, jamais une perte.

**Trois conséquences à connaître.**

1. **Un agent qui ne s'est pas déplacé ne consolide pas** — le plancher exige un tampon non vide —
   donc il n'entend pas le foyer ce soir-là. Il l'entendra à sa prochaine consolidation, matière
   intacte. On n'allume pas un appel LLM pour faire écouter quelqu'un qui n'a rien à dire.
2. **Un agent `immobile` n'entend jamais rien.** C'est cohérent : il ne décide de rien non plus.
3. Le repère de lecture est **persisté au point de reprise de 3 h**. Sans cela, une reprise à chaud
   ferait ré-entendre au foyer entier plusieurs nuits déjà entendues — le défaut que le 075 a
   corrigé pour la mémoire, à ne pas réintroduire par la porte du foyer.

Points d'accroche dans le code : `urban_mobility_agents/agents/llm_agent.py` (construction du
contexte de `stm_reflection`) et le gabarit
`packages/mobility_llm/src/mobility_llm/categories/stm_reflection/template.md.j2`.

---

## 3. Ce que le foyer raconte — le repère de lecture, et six règles

**Un repère par receveur, pas par foyer :** `foyer_lu_jusqu_a`, horodatage simulé de la dernière
consolidation où l'agent a entendu son foyer. C'est ce qui rend l'ordre des consolidations
indifférent, et la règle Q2 exacte : *tout ce qui a été ajouté ou modifié depuis la dernière
synchro*, pour **ce** receveur.

À la consolidation de B au temps T, le bloc rassemble, pour chaque autre membre M présent du même
`household.id`, les concepts de M qui satisfont :

| # | Règle | Pourquoi |
|---|---|---|
| R1 | **M l'a vu au moins deux fois lui-même** : `observations ≥ 1` | **La règle d'ancrage.** On ne raconte pas au foyer ce qu'on n'a pas vérifié. Un concept créé part à `observations = 0` — vérifié dans le code, seul un `confirmer` l'incrémente, donc seule une journée où l'agent a **revécu** la chose. Conséquence : une croyance née d'une conversation **ne peut pas repartir** dans le foyer tant que son porteur ne l'a pas ancrée dans un déplacement réel. Aucune amplification non ancrée n'est possible, par construction et sans un champ de plus. Seuil paramétrable (`memoire__partage_foyer_observations_min`, défaut 1) |
| R2 | **Jamais encore montré à B** — et reproposé seulement s'il a été **précisé** ou **mis hors service** depuis | La règle de l'auteur : *on ne partage que ce qui n'a jamais été partagé*. Une simple confirmation ne fait pas repartir un concept : sinon une croyance que son auteur confirme chaque jour serait servie chaque soir à toute la famille, et c'est exactement ce qu'une lecture naïve de `derniere_observation` produirait. Le compteur voyage en bagage (« vu 12 fois ») la prochaine fois que le concept repart pour une vraie raison. Trois horodatages existants portent la règle, **aucun champ nouveau** : `timestamp`, `derniere_observation`, `depasse_le` |
| R3 | `axe_objet` **renseigné** | Un concept sans axe n'est ni filtrable ni rangeable. Mesure du 077 : 211 concepts sur 231 en étaient dépourvus |
| R4 | Le mode du concept est **praticable par B** | Le cas Constance / Jacques. Réutiliser `modes_vehicules_eligibles(person, domicile)` — le verrou de possession et de permis existe déjà |
| R5 | Le bloc est **borné** (`memoire__partage_foyer_max_bloc`, défaut 12 énoncés) — **garde-fou, pas politique** | Avec R1 et R2, le volume attendu est petit : quelques énoncés par nuit. La borne n'est donc pas là pour rationner mais pour empêcher un emballement de passer inaperçu dans un prompt dont le 077, lot D, a mesuré qu'il stagne déjà à ~2 100 jetons. **Toute troncature se compte et s'alarme** : elle signale que quelque chose ne va pas ailleurs |
| R6 | M ≠ B, même `household.id`, membre **présent** dans la simulation | Un membre du ménage absent de la cohorte n'existe pas et ne raconte rien |

**R1 est la seule règle dirigée contre l'emballement, et elle ne coûte rien** — elle relit un
compteur qui existe déjà. ⚠ **Sa contrepartie est réelle et doit être mesurée dès le premier run :**
le 077 a compté 225 concepts sur 231 restés à zéro observation. Si le lot A du 077 ne fait pas
repartir les confirmations, R1 laisse le canal **vide**. Le nombre de concepts éligibles au partage
est donc la première chose à regarder (§ 6, mesure n° 1) — et le seuil est paramétrable pour qu'on
puisse le constater sans réécrire le code.

**Ce que porte chaque ligne du bloc** — et c'est la réponse Q4 : le concept est **attribué et
nommé**, avec l'âge.

```
Tonight at home
- Matéo (8) told you about their day: "the school bus is always full after 4 pm"
  — they have seen it 4 times
- Valérie (66) no longer believes: "parking near the market is easy in the morning"
```

⚠ **Le lien de parenté n'est pas dans les données.** EMC² et eqasim donnent l'appartenance au
ménage, l'âge et le genre — pas la filiation. Le bloc dit donc « un membre de votre foyer, Matéo,
8 ans », jamais « votre fils ». Inventer la parenté serait fabriquer une donnée, et elle
retomberait dans les prompts comme un fait.

⚠ **Le piège de R4 est celui du lot A du 077, sur une troisième route.** Trois vocabulaires
coexistent : les **modes canoniques** que le schéma de réflexion impose au modèle (`car`,
`cycling`, `walking`, `public_transport`…), les **étiquettes de jambes** de la hiérarchie AUAT
(`foot`, `bus`, `bicycle`), et `_VEHICLE_MODES = ("bike", "car")` de
`urban_mobility_agents/vehicle_chain.py`, qui est celui du verrou de possession. La table de
correspondance doit être **explicite et testée**, et un mode qui n'y figure pas **ne traverse
pas** — il se compte et s'alarme. Aucun repli permissif : un mot inconnu qui passerait « par
défaut » rendrait le verrou de permis décoratif.

Marche et transports collectifs ne sont écartés par aucun verrou de possession, ici comme dans
`eligibilite()` : ils traversent pour tout le monde.

---

## 4. Ce que B en fait — rien n'est écrit dans son dos

**Aucune écriture directe dans la mémoire de B.** Le bloc est une **entrée de l'appel**, au même
titre que les expériences de la journée. C'est le modèle, dans la réflexion de B, qui décide s'il
en tire une croyance — et le vocabulaire pour le dire existe déjà, inchangé depuis le lot 3 du
071 : `create`, `confirm`, `refine`, `contradict` sur les `known_beliefs`.

Trois conséquences, et elles sont le cœur du mécanisme :

1. **Ce que le foyer dit n'est pas une croyance de B tant que B n'en fait rien.** Une phrase
   entendue qui ne résonne avec rien disparaît avec l'appel. C'est le bon défaut : la mémoire ne
   grossit pas d'avoir écouté.
2. **Ce que B en tire est confronté à ce que B croit déjà**, dans le même appel, par le même
   mécanisme. Si Jacques dit que le 401 est ponctuel et que B a attendu vingt minutes, B
   **contredit** — et la contradiction est datée, donc lisible.
3. **Coût marginal nul en appels.** Le seul coût est en jetons d'entrée, borné par R4 et mesuré
   (§ 6).

### 4.1 Le mélange est libre, et rien ne le trace

Matéo, 8 ans, apprend que le bus n'est pas fiable, et le dit. Son père l'entend, le mêle à sa propre
journée, et forme une connaissance qui n'existait chez personne : *le bus n'est pas fiable pour
emmener les enfants à l'école*. **C'est exactement ce qu'on cherche** — et ce concept-là repart dans
le foyer comme n'importe quel autre, sans traitement de faveur ni marquage.

**Rien ne retient l'origine d'un concept. Aucun champ nouveau, aucune déclaration demandée au
modèle, aucune généalogie.** Une croyance née d'une conversation est une croyance comme les autres :
c'est ce qui se passe chez les gens, et c'est ce qui coûte le moins de code.

**Ce qui empêche l'emballement n'est donc pas une généalogie, c'est l'ancrage.** Deux règles
suffisent, et toutes deux relisent des compteurs qui existent déjà :

- **R2** — une même phrase n'est jamais montrée deux fois à la même personne ;
- **R1** — on ne raconte que ce qu'on a vu au moins deux fois soi-même.

R1 est ce qui ferme la boucle pour de bon, et il faut voir pourquoi. Le père, ayant entendu Matéo,
peut parfaitement écrire *« le bus n'est pas fiable pour les enfants »* : c'est sa pensée, elle a le
droit d'exister. Mais ce concept naît à **zéro observation**, donc il ne repart **pas** dans le
foyer. Il n'en repartira que le jour où le père aura lui-même conduit ses enfants et constaté la
chose — c'est-à-dire quand elle ne sera plus un ouï-dire. **Une croyance ne circule qu'ancrée dans
un déplacement réel**, et un cycle d'amplification sans contact avec le monde devient impossible
sans qu'on ait à tracer quoi que ce soit.

La formulation d'origine venait d'une relecture extérieure qui proposait un ensemble de
contributeurs par concept ; c'en est la version gratuite — même garantie, un compteur déjà écrit au
lieu d'un champ, d'un contrat de sortie et de deux chemins d'attribution.

> **Variante C, écartée pour l'instant.** Ne plus partager des croyances mais les **faits** de la
> journée, tirés de la simulation (« Matéo est allé à l'école en bus, le 62, 12 minutes de retard,
> sous la pluie »). La boucle y est structurellement impossible — ce qui circule ne vient jamais
> d'une mémoire. Écartée parce qu'elle change l'objet du ticket : le savoir accumulé ne traverserait
> plus, seulement les faits de la veille. À reprendre pour elle-même, pas par crainte des boucles.

**Pas d'héritage de compteurs.** Si B crée un concept à partir de ce qu'il a entendu, il part à
`observations = 0`, donc **confiance 0,50** — la valeur de Laplace pour ce qui n'a jamais été
vérifié. Les douze observations de Jacques sont l'expérience de Jacques ; les transmettre ferait
gagner de l'autorité à une croyance que personne d'autre n'a vue, et rendrait un foyer de cinq
mécaniquement plus sûr de lui qu'un célibataire. Ce serait une chambre d'écho avec une échelle de
confiance pour la légitimer.

**Le rang dans « Ce que je sais » ne change pas.** `noyau.bloc_connaissances` trie par
`(confiance, observations, date)`, et cela suffit : un concept né d'une conversation part à zéro
observation, il passe donc naturellement derrière tout ce que l'agent a vérifié lui-même. Il monte
s'il se confirme sur le terrain, et c'est la bonne règle. **Aucune clé de tri nouvelle, aucun
libellé de provenance** — le bloc du soir, lui, nomme déjà celui qui parle.

---

## 5. Le coût

**Zéro appel LLM supplémentaire**, par construction : il n'y a pas de passe, pas de prompt dédié,
pas de dialogue. Le surcoût est **en jetons d'entrée** sur un appel qui a déjà lieu.

Ordre de grandeur, à partir du run de 30 jours du 077 (231 concepts, 5 agents, 30 jours, soit
~1,5 concept par agent et par jour) : dans un foyer de quatre, un membre entend environ 4 à 5
énoncés par nuit, bornés à 12 par R4 — quelques centaines de caractères dans un prompt de
consolidation qui en fait déjà plusieurs milliers. Le contrat de test doit porter la mesure réelle,
pas cette estimation.

**L'écart d'échelle avec un dialogue, chiffré.** Ici, le coût par foyer et par nuit est de *n*
lignes de prompt dans des appels qui ont déjà lieu — **aucun appel nouveau**. Un dialogue entre
membres coûterait *n(n−1)/2* appels par nuit : six pour un foyer de quatre, vingt-et-un pour le plus
grand foyer de la cohorte. Sur les 287 ménages multi-membres de la v6, la différence n'est pas un
facteur, c'est un changement de nature : d'un côté quelques centaines de caractères, de l'autre une
campagne à budgéter. C'est ce qui rend le mécanisme tenable à mille agents, et c'est l'argument à
porter en cas de comparaison avec un protocole conversationnel.

---

## 6. Ce qui se mesure

Sans mesure, ce ticket produit une croyance de plus sur la mémoire — et le 077 vient de montrer ce
que valent les croyances non mesurées sur cette chaîne. À instrumenter dans le même geste que le
lot E du 077 :

1. **Ce qui est éligible, avant tout le reste** : combien de concepts passent R1 — c'est-à-dire
   combien ont été observés au moins deux fois par leur porteur. **À regarder au premier run avant
   toute autre chose** : si ce nombre est proche de zéro, le canal est vide et rien d'autre n'a de
   sens à mesurer. Puis, par consolidation : taille du bloc foyer (énoncés, caractères), membres
   représentés, concepts écartés **par règle** (R1 à R6, comptées séparément), troncatures R5.
2. **Ce que le foyer change à la consolidation** : opérations produites (`create`, `confirm`,
   `refine`, `contradict`) les nuits où le bloc est **non vide**, contre les nuits où il est vide.
   Aucune provenance n'est nécessaire pour ce chiffre, et c'est lui qui dit si écouter sert à
   quelque chose.
3. **La reformulation circulaire — le détecteur de la boucle.** Dans un même foyer et un même
   panier `(mode, motif)` : combien de concepts distincts coexistent, et combien de mots-clés ils
   partagent. Une famille qui redit la même chose sous quatre formes se voit d'un coup d'œil.
   ⚠ **Indicateur de lecture, jamais un seuil qui agit** : le 071 et le 077 ont tous deux refusé
   qu'une mesure de similarité décide à la place d'une règle. Celui-ci alerte un humain, il ne
   coupe rien tout seul.
4. **Ce qui n'a rien produit** : part des lignes de bloc qui ne déclenchent aucune opération. Si
   elle est haute, R2 se durcit — on ne l'invente pas avant.
5. **L'accord intra-ménage — l'hypothèse que ce ticket rend réfutable.** Sur les fiabilités perçues
   par mode (et par ligne quand elle est nommée), mesurer la divergence entre membres d'un **même**
   foyer et entre foyers **différents**, par divergence de Jensen-Shannon — la métrique est déjà
   dans le vocabulaire du dépôt. Prédiction à préenregistrer : *le partage réduit la divergence
   intra-ménage sans réduire la divergence inter-ménages*. Un foyer qui converge pendant que les
   foyers restent distincts, c'est un apprentissage collectif ; tout le monde qui converge vers la
   même chose, c'est le modèle qui parle, pas les agents.
   ⚠ **Garde-fou de vacuité, non négociable.** Sur deux agents porteurs de trois concepts chacun,
   un accord se calcule sur presque rien et peut sortir **parfait par absence de matière** — le
   motif est connu dans ce dépôt, et il a déjà produit des scores parfaits qui ne mesuraient rien.
   Effectif minimal déclaré, et verdict **« non concluant »** en dessous, sur le modèle de
   `slope_verdict` au [031](ticket_031_perimetre_453_communes.md). Un « non concluant » est un
   résultat ; un 0,0 obtenu sur trois concepts est un mensonge.
6. **Journal** (`memoires/<id>.md`, dispositif du 075) : à chaque consolidation, ce que le foyer a
   dit, qui l'a dit, et ce que l'agent en a fait — la même forme que les opérations de concept.

**Ces mesures sont la contrepartie de la simplicité du § 4.1.** R1 garantit qu'aucune croyance ne
circule sans ancrage dans le monde ; elle ne garantit pas que le foyer apprenne quoi que ce soit, ni
qu'il ne se répète pas. Sans les mesures 1 à 5, tout le reste est un pari, et le ticket perd le
droit de s'en réclamer.

---

## 7. La population de test — et pourquoi celle du 075 ne convient pas

**Mesuré :** les cinq agents de `population_5_memoire_075` appartiennent à **cinq ménages
distincts** (312, 407431, 273701, 5177, 18056). Le mécanisme de ce ticket y serait strictement
inobservable. Il faut le dire avant de lancer quoi que ce soit.

Or ces cinq-là **ont** des colocataires dans la v6, et ils sont douze en tout :

| Ménage | Membres présents en v6 |
|---|---|
| 312 | Xavier Briand (40) — **seul : témoin interne, le partage ne doit rien lui faire** |
| 5177 | Constance Ledoux (12, sans permis, sans vélo) · Jacques Aubert (49, permis, vélo) |
| 18056 | Valérie Duhamel (66) · Maurice de la Evrard (65) |
| 407431 | Corinne de la Richard (53, abonnement TC) · Laetitia Bigot (12) · Léon Bouvier-Grégoire (54) |
| 273701 | Adrienne Bonneau du Lejeune (59, abonnement TC) · Simone Roussel (23) · Colette-Odette Moreno (24) · Thierry de la Baudry (23) — **quatre sans voiture ni vélo** |

**Lot 0 : `population_12_foyers_078`**, extraite par
`scripts/data/population/extraire_sous_population.py`, avec un `MANIFEST.yaml` sur le modèle du
075 et la même mention en tête : *ce n'est pas un sceau, douze agents ne mesurent aucune part
modale*. La continuité avec le 075 et le 077 est entière — les cinq journaux déjà lus restent
lisibles et comparables — et le foyer 312 fournit le témoin qui ne partage avec personne.

---

## 8. Ordre et dépendances

1. **Le 077 en entier d'abord.** Deux raisons, chiffrées :
   - sans le **lot A**, `axe_objet` est vide sur 211 concepts sur 231 : R2 écarterait 91 % des
     concepts et R3 n'aurait rien à filtrer — le foyer ne raconterait presque rien, et le peu
     qu'il raconterait échapperait au verrou de possession ;
   - sans le **lot B**, les concepts de la journée portent des marches de cinq à douze heures qui
     n'ont pas eu lieu. Les raconter au foyer reviendrait à contaminer tout le monde avec le bug
     d'un seul. **Partager une mémoire fausse est pire que ne pas partager.**
2. **Lot 0** — la population de douze. Indépendant, faisable avant.
3. **Lot 1** — repère `foyer_lu_jusqu_a` (persisté au point de reprise), construction du bloc, six
   règles, drapeau. Testable sans run.
4. **Lot 2** — gabarit de consolidation : le bloc et son instruction. **Rien d'autre** : ni champ
   de sortie nouveau, ni changement de tri dans le noyau, ni schéma touché.
5. **Lot 3** — instrumentation et journal (§ 6).
6. **Lot 4** — deux runs sur `population_12_foyers_078`, mêmes graines de tirage et de météo,
   drapeau à `false` puis à `true`. Sans le run témoin, aucune différence observée n'est
   attribuable — c'est la leçon du lot E.6 du 077.

---

## 9. Ce que ce ticket refuse, et pourquoi

**Refusé : un dialogue LLM entre membres du foyer.** C'est la voie évidente — Park et al. (2023)
font diffuser l'information entre agents par la conversation — et c'est un appel par paire et par
nuit, soit six appels quotidiens dans un foyer de quatre pour transporter trois phrases. Le
mécanisme du § 4 fait la même chose dans un appel **qui a déjà lieu** : la consolidation *est* la
conversation du soir. À rouvrir seulement si la mesure n° 2 du § 6 montre que ce qui est entendu ne
devient jamais rien.

**Refusé : écrire dans la mémoire de B sans passer par sa réflexion.** Une croyance qu'on n'a ni
formulée ni confrontée n'est pas une croyance, c'est une injection.

**Refusé : hériter des compteurs de la source.** Chambre d'écho, § 4.

**Refusé : partager les épisodes.** § 1.

**Refusé : renommer le mécanisme pour échapper à une comparaison.** Une relecture extérieure
proposait de le présenter comme une *stigmergie sociale asynchrone* plutôt que comme une
conversation du soir, afin d'éviter le rapprochement avec Park et al. (2023). Deux raisons de ne
pas le faire. D'abord le terme serait **inexact** : la stigmergie est une coordination par des
traces laissées dans l'environnement, alors qu'ici ce qui circule vient de la mémoire interne d'un
autre agent — un relecteur attentif le relèvera, et il aura raison. Ensuite on n'échappe pas à un
travail voisin en changeant de vocabulaire : on le cite et on dit en quoi on diffère. La différence
est d'ailleurs chiffrable, elle est au § 5, et elle est plus solide qu'un nom.

**Refusé : toute machinerie de généalogie anti-boucle.** L'ancrage de R1 offre la même garantie —
aucune amplification sans contact avec le monde — en relisant un compteur déjà écrit. Reste, en
dessous de cette garantie, la seule question ouverte : celle de la
reformulation circulaire d'un concept **déjà ancré**, qui reste possible et qui **se mesure**
(§ 6, n° 3) avant qu'on lui oppose quoi que ce soit. Deux versions plus lourdes ont été écrites puis
retirées le 2026-09-15 : interdire de partager ce qu'on a entendu — qui interdisait du même coup de
mêler l'entendu au vécu, c'est-à-dire l'objet même du ticket — puis une généalogie des contributeurs
à chaque concept, avec déclaration du modèle et filet automatique.

**Refusé : inventer le lien de parenté.** § 3.

**Refusé : étendre le canal aux collègues, aux voisins ou à la commune.** Le foyer est le seul
groupe qui porte un identifiant **dans les données**. Tout le reste demanderait un graphe social
inventé, et un graphe inventé produit des résultats qui parlent du graphe, pas des agents.

**Refusé : la déduplication par similarité cosinus.** Le lot 3 du 071 l'a rejetée en toutes lettres
et le § 7 du 077 a refusé de la rouvrir. Si le foyer crée des doublons, ils se règlent là où les
doublons se règlent déjà : dans `known_beliefs`, à la consolidation suivante.

---

## 10. Ce que ce ticket ne fait pas

Il ne touche **aucune règle** de la mémoire : ni gravité, ni oubli, ni viviers, ni score composite,
ni opérations de concept, ni seuils. Il ne modifie pas la cohorte scellée v6 et n'en consomme aucun
jeu gelé. Il ne traite pas la **négociation** de la voiture du foyer — c'est le
[018](ticket_018_partage_voiture_foyer.md), un objet rival, un tout autre problème. Il ne produit
aucun chiffre pour l'article : douze agents observent un mécanisme, ils ne mesurent pas une part
modale, et `population_1000_AAMAS_v6` reste la référence.

**Impact article, le jour de la livraison et pas avant.** Un canal entre agents modifie la
description de l'architecture cognitive et la table d'ablation ; le signalement se fera par la
skill `article-impact` au moment où le code existe, pas à l'ouverture du ticket.

**Condition d'entrée dans l'article, écrite ici pour qu'elle ne se décide pas en passant.** Aucun
chiffre de ce ticket n'entre dans le papier sans un run comparatif sur la **cohorte v6 entière**,
deux bras à graines identiques, drapeau à `false` puis à `true`. Ce run n'est **pas un lot de ce
ticket** : c'est une campagne, et son ordre de grandeur le dit — 1 000 agents × 30 jours × ~3,3
déplacements font ~100 000 décisions par bras, plus 30 000 consolidations, le tout à doubler. Il se
budgète en quotas, il passe par la plateforme d'expériences, et il ne se lance pas avant que les
douze agents du § 7 aient montré que le mécanisme produit un effet. Deux avertissements de méthode
qui vont avec : une campagne de cette taille **prend la place** de tout run manuel en cours ; et
l'ambition déclarée de l'article sur la mémoire est celle d'un élément parmi d'autres, non d'une
preuve causale isolée — une ligne d'ablation de plus est une promesse, et elle se décide, elle ne
s'ajoute pas parce qu'un relecteur la suggère.

---

## 11. Décisions de l'auteur, 2026-09-15

| # | Question posée à l'ouverture | Réponse, et où elle s'applique |
|---|---|---|
| Q1 | Quand la passe a-t-elle lieu ? | **En même temps que la consolidation journalière** — il n'y a pas de passe. § 2 |
| Q2 | Quelle fenêtre de partage ? | **Tous les concepts ajoutés ou modifiés depuis la dernière synchro familiale.** R2, portée par `timestamp`, `derniere_observation` et `depasse_le` — aucun champ nouveau |
| Q3 | Un concept entendu peut-il servir une décision avant vérification ? | Question mal posée. **Le concept du foyer est une ENTRÉE de la consolidation** : consolidation journalière = expériences personnelles + apports du foyer. Rien n'entre en mémoire sans passer par la réflexion de l'agent. § 4 |
| Q4 | Partage symétrique ou orienté ? | **Symétrique, et la source est nommée** : « Matéo (8) vous raconte sa journée ». § 3 |
| Q5 | Un prompt dédié ? | **Non — intégré à la consolidation.** § 2 et § 4 |

### Deuxième tour, 2026-09-15 — ce que l'auteur a corrigé dans le mécanisme

| Point | Ce qui était écrit | Ce qui est arrêté |
|---|---|---|
| **P1 — la boucle** | « On ne relaie pas ce qu'on a entendu », puis une généalogie des contributeurs par concept | **Les deux retirées.** La première interdisait de mêler l'entendu au vécu, donc la consolidation collective elle-même ; la seconde était une usine à gaz contre un phénomène jamais observé. Il ne reste que R1 — jamais deux fois la même chose à la même personne — et **une mesure** (§ 6, n° 3). La parade minimale est décrite en réserve, avec sa condition de pose |
| **P2 — le volume** | Une borne à 12 énoncés, posée par défiance | La règle de l'auteur est « seulement ce qui n'a jamais été partagé » (R1), et le volume attendu est petit. La borne **reste**, requalifiée en garde-fou journalisé : elle ne rationne pas, elle signale |
| **P3 — le genre** | Gabarit neutre, sans justification | Le genre n'interviendrait **qu'au pronom** de la phrase d'introduction du bloc — jamais dans un filtre, une décision ou une mesure. Neutre par défaut, accordable en une ligne de gabarit si l'auteur le souhaite |

### Troisième tour, 2026-09-15 — relecture extérieure

Quatre recommandations reçues. Ce qui en est retenu, et ce qui ne l'est pas.

| Recommandation | Décision |
|---|---|
| **Poser d'office une règle d'origine** (`source_members` par concept, jamais rediffusé à un contributeur tant que l'agent ne l'a pas validé par un déplacement) | **Retenue dans son intention, refusée dans sa forme.** L'intention est juste et c'est la bonne attaque : ce qui est attaquable n'est pas la boucle, c'est qu'une croyance circule sans que personne ne l'ait vérifiée. Mais la forme réintroduit la généalogie et laisse de côté le point dur — comment remplir cet ensemble quand le modèle a reformulé la phrase. **La clause finale de la recommandation donne la version gratuite** : `observations ≥ 1`, un compteur déjà écrit. C'est R1 |
| **Reformuler en « stigmergie sociale asynchrone à bande passante bornée »** pour éviter la comparaison avec Park et al. | **Refusée** — terme inexact et stratégie perdante, § 9. **L'argument d'échelle qui l'accompagnait est retenu** et chiffré au § 5 : *n* lignes de prompt contre *n(n−1)/2* appels |
| **Mesurer l'accord intra-ménage** (JSD), hypothèse : réduire la variance intra-ménage sans détruire la diversité inter-ménages | **Retenue telle quelle** — c'est ce qui transforme le ticket en hypothèse réfutable. Avec un garde-fou de vacuité obligatoire, § 6, n° 5 |
| **Ajouter un lot de validation macro** sur la v6 entière, deux bras, pour la table d'ablation du papier | **Différée, et écrite comme condition d'entrée** au § 10 — pas comme un lot. C'est une campagne (~100 000 décisions par bras), elle se budgète, et elle ne se lance pas avant que les douze agents aient montré un effet |

### Ce qui reste ouvert


- **Le canal peut naître vide.** R1 n'a de sens que si les confirmations repartent après le lot A
  du 077 ; le 077 a compté 225 concepts sur 231 à zéro observation. La mesure n° 1 du § 6 tranche
  dès le premier run, et le seuil est paramétrable pour qu'on puisse le constater sans toucher au
  code.
- **La reformulation circulaire d'un concept déjà ancré reste possible.** R1 interdit l'amplification
  hors-sol, pas qu'une même idée vérifiée soit redite autrement par trois membres. Mesure n° 3, et
  rien de plus tant qu'elle n'a rien montré.
- **Le seuil de la mesure n° 4** — au-delà de quelle part de lignes stériles la règle R1 se durcit,
  et en quoi.
- **La variante C reste sur la table pour elle-même** : partager les faits de la journée plutôt que
  les croyances. Elle ne se choisit pas contre les boucles, elle se choisit si l'on juge qu'un
  foyer se raconte ce qu'il a vécu, et non ce qu'il en conclut.
