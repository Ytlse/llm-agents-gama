# Ticket 057 — Audit méthodologique et réflexion sur la double lecture tabulaire en chaîne vs hors chaîne (Chapitre 6 § 6.2)

> ## ✅ CLOS le 2026-09-16 — les cinq critères remplis
>
> L'écart entre les deux lectures ne venait pas de la règle de chaîne, qui est conforme au
> terrain à 98,5 %, mais du **périmètre de score** : la coupe au premier jour simulé retirait
> 866 décisions sur 3 299 pour zéro doublon, dont 797 départs du matin que `jeu.py` datait du
> lendemain. Corrigé aux deux endroits, 25 exécutions rescorées, chapitres 4 et 6 repris.
>
> Suites ouvertes ailleurs : [ticket 088](ticket_088_jeu_corrige_et_rejeu_complet.md) (jeu à
> re-préparer, rejeu complet) et [ticket 087](ticket_087_attribution_du_nombre_de_voitures_par_menage.md)
> (filière du nombre de voitures). Le détail de la clôture est en fin de fichier.

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 14 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Nature du ticket** : **Tâche de réflexion critique, d'audit méthodologique et de vérification expérimentale « ceinture et bretelles ».** Avant d'affirmer dans le papier que l'écart entre lecture en chaîne et hors chaîne prouve le coût de l'absence d'anticipation de la journée, il est impératif d'auditer la méthode, de contrôler l'acceptabilité des chiffres et de vérifier qu'aucun biais de mesure n'explique cette dégradation. Les conséquences rédactionnelles ne seront tirées qu'après validation.

---

## 1. Contexte & Questionnements

Les exécutions récentes sur la cohorte scellée v5 font apparaître une dégradation brutale des 4 familles tabulaires lorsqu'elles passent du mode « hors chaîne » au mode « en chaîne » :
- **Hors chaîne** (`nochn_noret_nosim`) : les 4 modèles sont très proches et stables (Composite entre $4{,}18$ et $4{,}45$, Métrique 2 entre $3{,}97$ et $4{,}18$, environ $1{,}4\,\%$ de décisions contraintes).
- **En chaîne** (`nosim`) : la Métrique 2 (distribution des parts) fait un bond spectaculaire vers le haut (LightGBM : $10{,}46$ ; KLR : $9{,}95$ ; MNL : $11{,}15$ ; RF : $10{,}45$), avec plus de $20\,\%$ de décisions contraintes au retour.

Avant d'ériger cet écart en résultat scientifique central dans l'article, nous devons appliquer le principe d'exigence absolue : **« ceinture et bretelles »**. 
- Ces résultats sont-ils acceptables et plausibles ? 
- N'y a-t-il pas un problème dans l'implémentation de la règle de chaîne dans le runner ?
- Le traitement des trajets de retour contraints est-il méthodologiquement irréprochable ou introduit-il une distorsion artificielle ?

---

## 2. Programme d'Audit et de Réflexion Méthodologique

### 2.1 Audit de la chaîne d'application des contraintes dans le code
* **Vérification du runner sans simulateur** :
  - Examiner le mécanisme qui impose le mode au retour dans `services/llm-agents/experiences/runner.py` (ou script équivalent) : comment l'état de localisation du véhicule est-il mis à jour et vérifié ?
  - La proportion de $\approx 20{,}8\,\%$ de décisions contraintes observée en chaîne correspond-elle exactement à la structure réelle des chaînes d'activités des personas, ou y a-t-il des blocages indus ?
* **Examen du dénominateur et de la renormalisation** :
  - Quand un modèle tabulaire est confronté à un retour contraint (ex. obligation de rentrer en voiture car la voiture est au travail), la décision est-elle comptée comme un choix scoré ou comme une exclusion ?
  - La Métrique 2 calcule-t-elle les parts modales sur l'ensemble des trajets ou seulement sur les trajets où une délibération réelle avait lieu ? Vérifier l'impact mathématique exact de cette convention sur le saut de $4{,}01$ à $10{,}46$.

### 2.2 Contrôle qualitatif sur cas d'échantillons
* **Audit unitaire de 30 parcours d'agents** :
  - Extraire 30 chaînes complètes de déplacements d'agents pour chaque famille tabulaire (LGBM, RF, KLR, MNL).
  - Contrôler pas à pas : les décisions prises le matin étaient-elles raisonnables ? Les impasses créées au retour sont-elles des situations urbaines réalistes (ex: navetteur parti en voiture et contraint de rentrer avec) ou des artefacts de code ?

### 2.3 Évaluation de la validité scientifique de la double lecture
* **La comparaison est-elle juste ?**
  - Un modèle tabulaire ajusté sur des microdonnées d'enquête (où les personnes réelles respectaient déjà les chaînes) n'est-il pas intrinsèquement pénalisé deux fois lorsqu'on lui réapplique le filtre ?
  - L'écart mesuré reflète-t-il fidèlement le coût de la myopie temporelle, ou un artefact de sur-contrainte ?

---

## 3. Ce que le ticket livre

1. **Rapport d'audit technique et méthodologique sur la double lecture** : diagnostic tranché sur l'absence de biais dans l'implémentation des contraintes en chaîne.
2. **Recommandations d'interprétation pour le Chapitre 6** :
   - Si les chiffres sont validés sans faille : définir le cadrage honnête et prudent à adopter dans l'article.
   - Si un biais ou un problème de mesure est détecté : corriger le runner et re-mesurer avant toute écriture.

## Critères de clôture
- [ ] Le code appliquant les contraintes de chaîne dans le runner a été audité et validé.
- [ ] L'impact de la part des décisions contraintes (~20 %) sur la Métrique 2 est formellement expliqué et quantifié.
- [ ] L'échantillon de parcours individuels a été inspecté sans déceler d'incohérence.
- [ ] Aucune affirmation péremptoire n'est rédigée dans le texte du chapitre 6 avant la clôture formelle de cet audit.

---

## Mesure du 2026-09-16 — le mécanisme est le retrait de l'offre, pas le retour forcé

Ventilation des 2 340 décisions scorées du 16 mars 2026, run
`exp_lgbm_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_nosim/executions/2026-09-14_22_43_05`,
par valeur de `contrainte_chaine` dans `decisions.jsonl` (parts de masse, en %) :

| groupe | n | part | voiture | marche | TC | vélo |
|---|---:|---:|---:|---:|---:|---:|
| libres | 909 | 39 % | 45,4 | 35,8 | 16,5 | 2,3 |
| `sortie_bloquee` | 668 | 29 % | 22,0 | 53,7 | 23,3 | 1,0 |
| `retour_force` | 592 | 25 % | 93,6 | 0,0 | 0,0 | 6,4 |
| `passager` | 171 | 7 % | 60,0 | 21,9 | 16,9 | 1,2 |
| **ensemble** | 2 340 | | **52,0** | 30,8 | 14,3 | 2,9 |
| même run, hors chaîne | 2 341 | | 57,9 | 26,0 | 12,3 | 3,8 |
| cible EMC² | | | 56,7 | 26,8 | 12,4 | 4,1 |

Trois constats pour l'audit du § 2.1.

1. **La contrainte retire plus de voiture qu'elle n'en impose.** Le poste dominant est
   `sortie_bloquee` (29 % des décisions), où le véhicule possédé n'est pas au point de
   départ : la voiture sort de l'offre et la masse part sur la marche et les TC. Les
   592 retours contraints ne compensent pas. Solde : **−5,9 points de part voiture**.
2. **31 % des décisions scorées ne portent aucune distribution** sous chaîne (722 sur
   2 340, dont les 592 retours forcés), contre 30 hors chaîne. Elles entrent dans les
   parts comme si le décideur les avait produites. C'est une part de l'écart de composite
   (35,7 → 53,3) qui est imputable à la convention de score, non au décideur.
3. **Aucun effet de sélection : l'écart est intégralement imputé.** Les décisions ont été
   appariées sur `(person_id, activity_id)` entre les deux runs. **Valeurs rescorées après la
   correction du périmètre de score** (3 154 décisions, et non plus 2 340) : sur les 1 665
   déplacements que la règle laisse libres, les deux lectures donnent la **même** part voiture.
   Sur `sortie_bloquee` (674 déplacements), elle passe de 47,9 à 16,5 % ; sur `retour_force`
   (595), de 85,7 à 93,4 % seulement, l'oracle ayant déjà choisi la voiture pour l'essentiel
   de ces retours. Le verrou de sortie retire 212 déplacements en voiture, le verrou de retour
   en rend 46 et le mode passager 23, solde 4,5 points de part voiture. **Le verrou de retour
   n'apporte presque rien, le verrou de sortie fait tout l'écart** : c'est sur lui que porte
   l'audit. Les valeurs d'avant rescoring étaient 50,3 → 22,0 %, 85,7 → 93,6 % et −5,9 points.

   **Ce détail ne figure plus dans l'article** (décision de l'auteur du 2026-09-16) : la lecture
   sans contrainte de chaîne ne s'y publie plus, le run restant un instrument interne. Ce ticket
   est le seul porteur du chiffre.

4. **Ce qui reste à mesurer, et qui tranche le ticket.** Compter les décisions contraintes
   dans les parts est légitime : la journée a eu lieu, et l'enquête n'interroge pas que des
   personnes qui avaient le choix. La question est donc de savoir si **notre taux de
   contrainte ressemble au taux réel**. Mesure à faire sur les microdonnées EMC² : pour les
   personnes d'un ménage motorisé, la part des déplacements faits sans la voiture, et les
   situations d'indisponibilité du véhicule. Si notre 29 % de `sortie_bloquee` dépasse
   nettement ce que l'enquête montre, la règle sur-restreint et c'est démontré.
   **Mesure faite** le même jour — § 2.3 de l'audit ci-dessous : 4,2 % dans l'enquête contre
   18,0 % sur la journée entière du modèle. Le ticket 086, ouvert pour la commander, a été
   rejeté comme doublon et son reliquat est repris en fin de ce ticket.

Lecture retenue en attendant la clôture : la lecture sous chaîne compare des décideurs
soumis à la même règle d'offre — l'agent LLM comprise — et ne mesure pas un écart au
territoire. La cible EMC² décrit des journées déjà chaînées, sur lesquelles les quatre
familles sont ajustées ; la règle de chaîne (v1 de `docs/arch/vehicle-chain.md`, sans
`household_id`, sans trajet d'accompagnement généré, sans retour au domicile en milieu de
journée) l'applique une seconde fois sous forme approchée.

---

## Audit complet du 2026-09-16 — baseline v6

Rapport, scripts rejouables et sorties brutes :
`docs/traces/2026-09-16_08-51_ticket057_audit_double_lecture/` (hors git, doctrine des traces).
Périmètre : les huit exécutions du 2026-09-14 des quatre témoins tabulaires, en chaîne
(`nosim`) et hors chaîne (`nochn_noret_nosim`), cohorte `population_1000_AAMAS_v6`, jeu
`…_20260316_EN`. Aucune exécution relancée, aucun appel LLM.

### § 2.1 — le runner applique la règle qu'il annonce ✅

Une seule implémentation (`urban_mobility_agents/vehicle_chain.py`), partagée par la
simulation GAMA et le mode sans simulateur via `experiences/decision.py:eligibilite()`.
`planning_vehicle_at` est remis à vide en début de journée (`runner.py:596`) et avancé après
chaque décision, resservies de reprise comprises. 75 tests passent sur ce périmètre
(`test_071_lot1_chaine`, `test_045_02/07/12`, `test_035_02`, `test_047`).

Fait de mécanique non écrit jusqu'ici : **tout retour forcé devient un choix unique**. Chez
`lgbm`, les 592 décisions portant `contrainte_chaine = retour_force` sont les 592 décisions
journalisées « Un seul itinéraire disponible ». Le verrou ne restreint pas le choix, il le
supprime — le jeu ne propose au plus qu'un itinéraire par mode véhiculé. Le décideur n'est
donc jamais interrogé sur un retour véhiculé.

**Aucun effet de sélection.** Apparié sur `(person_id, activity_id)` entre les deux bras, sur
les quatre témoins : sur les déplacements que la chaîne laisse libres (916 chez `lgbm`,
915 `klr`, 914 `mnl`, 913 `rf`), **les deux bras prennent exactement les mêmes décisions, zéro
différence**. Le constat 3 de la mesure du 16/09 ci-dessus comparait 916 déplacements sous
chaîne à 2 341 hors chaîne — deux ensembles différents. Point instruit, réfuté.

| groupe (`lgbm`) | n | décisions différentes | part voiture sous chaîne → hors chaîne |
|---|---:|---:|---|
| libre | 916 | **0** | 39,8 → 39,8 |
| `sortie_bloquee` | 668 | 290 | 16,5 → 47,9 |
| `retour_force` | 592 | 94 | 93,6 → 85,8 |
| `passager` | 171 | 23 | 100,0 → 86,5 |

### § 2.3 — la règle est conforme au terrain ✅

Mesuré sur EMC² Toulouse 2023 (PROGEDO lil-1750, 54 585 déplacements, pondéré COEP), en
suivant le véhicule de lieu en lieu le long de chaque chaîne déclarée
(`scripts/mesurer_enquete.py`) :

| | enquête | modèle (`lgbm`, chaîne) |
|---|---:|---:|
| retours au domicile avec voiture sortie, faits en voiture | **98,5 %** | 100 % (règle dure) |
| idem vélo | 93,8 % | 100 % (règle dure) |
| part de ces retours dans tous les déplacements | **18,2 %** | **18,0 %** (journée entière) |
| déplacements partant d'un lieu où la voiture n'est pas | **4,2 %** | 22,6 % |
| journées de conducteur incohérentes avec la chaîne | 2,4 % | — |

Le verrou de retour n'est donc pas une sur-contrainte : il impose à 100 % ce que le terrain
fait à 98,5 %. Et la proportion de décisions contraintes coïncide avec l'enquête sans avoir
été ajustée sur elle. Le blocage de sortie, lui, est cinq fois plus fréquent que dans la
réalité : c'est le coût de la non-anticipation, et il se mesure **directement**, sans passer
par l'écart entre deux lectures.

### § 2.1 — le périmètre de score, lui, est biaisé ⚠

`frames.read_moves(first_day_only=True)` ne garde que le plus petit jour simulé du
`moves.csv`. Sur ces exécutions elle retire **866 décisions sur 3 299**, dont **797 sont le
déplacement de rang 0** de chaque personne — le départ du matin depuis le domicile.

Cause, identique sur les huit exécutions et indépendante du décideur : dans
`experiences/jeu.py:deplacements_attendus()`, l'instant de départ est résolu contre
`maintenant = base + precedente.start_time`. Pour la première paire de la journée,
`precedente` est l'activité « home » qui enjambe minuit — `start_time` 72 449 s (20:07) chez
la personne 609 — et la cible du matin (08:59) lui est antérieure : `if depart < maintenant:
depart += 86400`. Le départ du matin est daté du lendemain, puis écarté par la coupe.

**Aucun couple (personne, activité) n'est dupliqué** dans ces exécutions : la coupe, conçue
pour absorber les répétitions d'un horizon glissant en simulation, ne retire ici que des
déplacements uniques — et majoritairement en voiture (50,7 %), décidés librement (791 sur 866).

| | journée entière | périmètre scoré | enquête |
|---|---:|---:|---:|
| part des retours au domicile | 43,8 % | **56,9 %** | 39,0 % |
| part des retours forcés | 18,0 % | **24,3 %** | 18,2 % |

### § 2.1 — effet chiffré sur les deux lectures

Composite EMD, formule `v1_reference`, sans relancer aucune exécution :

| témoin | bras | scoré jour 1 | jour 1 hors CU | journée entière | journée entière hors CU |
|---|---|---:|---:|---:|---:|
| lgbm | chaîne | 4,40 | **10,04** | 3,63 | **5,87** |
| lgbm | hors chaîne | 4,20 | 4,03 | 3,72 | 3,55 |
| klr | chaîne | 4,44 | **9,51** | 3,57 | **5,52** |
| klr | hors chaîne | 4,22 | 3,99 | 3,66 | 3,46 |
| mnl | chaîne | 4,82 | **10,57** | 4,01 | **6,50** |
| mnl | hors chaîne | 4,32 | 4,18 | 3,91 | 3,78 |
| rf | chaîne | 5,05 | **10,14** | 4,19 | **5,97** |
| rf | hors chaîne | 4,57 | 4,36 | 4,18 | 3,98 |

**L'écart entre les deux lectures perd 60 %** sur la journée entière (`lgbm` : +5,64 → +2,24).
**L'écart entre les deux bras disparaît** : 3,63 contre 3,72 pour `lgbm`, 3,57 contre 3,66 pour
`klr`, 4,19 contre 4,18 pour `rf` — la chaîne ne dégrade pas le composite, et le bras sous
chaîne est même devant sur trois témoins sur quatre.

Le reste de l'écart entre lectures est arithmétique : la seconde lecture retire un
sous-ensemble à 93,6 % en voiture, et compare le reste (42,5 % de voiture) à une cible EMC²
qui en attend 55,9 %. La cible correspondant à ce périmètre existe et se calcule sur
l'enquête — **48,3 % de voiture hors retours contraints** — mais ce n'est pas elle que le
scoreur utilise.

### Deux points de journal, sans effet sur les scores

- La colonne « Modes proposés au LLM » porte l'offre **brute** du jeu, pas les présentées
  (`journal.py:138`, intentionnel et documenté). `bi_oracle.py:193` filtre sur
  `len(offered) < 2` pour écarter les décisions non délibérées : ce filtre ne peut pas voir
  les choix uniques créés par la chaîne. Ils sont bien écartés, mais par le chemin voisin
  `sans_distribution`. La protection tient par effet de bord.
- La mesure du 16/09 ci-dessus cite « 35,7 → 53,3 » : ce sont les composites **L1**, pas les
  EMD que cite le chapitre 6. Sur la même exécution, l'EMD va de 4,20 à 4,40.

### Critères de clôture — état

- [x] Le code appliquant les contraintes de chaîne dans le runner a été audité et validé.
- [x] L'impact de la part des décisions contraintes sur la seconde lecture est expliqué et
      quantifié — et sa cause principale est le périmètre de score, pas la règle.
- [x] L'échantillon de parcours a été inspecté : contrôle porté aux 894 personnes plutôt qu'à
      30, par appariement et par invariant de chaîne.
- [ ] Rien n'est écrit dans le chapitre 6 : signalement d'impact rendu, six points, aucune
      correction appliquée.
- [ ] Reliquat du ticket 086 (rejeté) : la mesure du § 2.3 est rejouée avec les helpers
      partagés de `vehicle_chain.py`, blocages à tort isolés, ventilés par motif et par
      couronne de résidence.

### Ce que l'audit ne tranche pas

Le bras `nochn_noret` coupe **les deux** règles à la fois. On ne sait donc pas séparer le coût
de la non-anticipation (sortie bloquée : le décideur choisit encore, dans une offre amputée)
de celui du retrait pur du choix (retour forcé : le décideur ne choisit plus). Les deux
réglages sont indépendants dans le code (`cli.py:92-93`) et le nommage prévoit déjà le jeton
`noret` seul (`nommage.py:381-383`).

**Expérience proposée** — quatre bras `noret` seuls, `vehicule_chaine: true` et
`verrou_retour: false`, un par témoin, même cohorte et même jeu :
`exp_{lgbm,klr,mnl,rf}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_noret_nosim`. Aucun appel LLM,
33 s par bras (durée mesurée du `lgbm` du 14/09), aucune ligne de code.

### Correction du 2026-09-16 — la myopie ne concerne PAS les agents

Remarque de l'auteur, vérifiée dans le code et chiffrée. Le décideur LLM reçoit l'agenda
glissant de sa journée (`experiences/decideurs.py:317` → `_build_anticipation`, produit pour
les seuls personas ayant un véhicule à chaîner). Le décideur `modele` ne lit jamais
`ctx.anticipation` : ses entrées sont l'origine, la destination, l'heure, le motif et les
21 variables. **La myopie est une propriété des familles tabulaires, pas des agents.**

La fréquence des sorties bloquées le montre, et elle s'ordonne (journée entière ; colonne
comparable à l'enquête restreinte aux personnes ayant pris la voiture au moins une fois) :

| décideur | sortie bloquée (conducteurs) | retours contraints |
|---|---:|---:|
| **enquête EMC² 2023** | **4,2 %** | 18,2 % |
| agent, prompt expert `gemini-3.5` (pe06/pe05/pe04) | **13,8 – 15,4 %** | 19,1 – 19,3 % |
| agent, prompt expert `gemini-3.1`, `mistral-large` | 17,3 % | 16,6 – 17,6 % |
| **familles tabulaires** (klr, mnl, rf, lgbm) | **17,7 – 18,0 %** | 17,8 – 18,1 % |
| agent, prompt minimal (palier 1) | 18,7 – 18,9 % | 14,7 – 16,7 % |
| plancher aléatoire | 30,9 % | 4,4 % |

Trois lectures.

1. **L'agent calibré se coince moins souvent que les tabulaires** — 13,8 à 15,4 % contre 17,7
   à 18,0 %. L'agenda sert, et c'est mesurable.
2. **Le prompt minimal ne sert à rien de ce point de vue** : 18,7 – 18,9 %, soit le niveau des
   tabulaires ou légèrement pire. Ce n'est donc pas « voir l'agenda » qui suffit, c'est la
   consigne calibrée qui apprend à s'en servir. Le gradient palier 1 → palier 2 vaut ici
   environ 4 points.
3. **Tout le monde reste très loin du terrain** (4,2 %). Une part de cet écart tient à notre
   règle, plus dure que la vie : pas de second véhicule du ménage, pas de conjoint qui ramène
   la voiture, pas de trajet d'accompagnement généré — dans l'enquête, 2,4 % des journées de
   conducteur sont d'ailleurs « incohérentes » au sens de notre règle, pour ces raisons-là.
   La mesure majore donc un peu la myopie ; elle ne l'invente pas.

Mesure : `scripts/mesurer_anticipation.py`, sortie `donnees/anticipation.json`.
Le chiffre « 22,6 % » cité plus haut dans la première passe de l'audit valait pour `lgbm` sur
le périmètre tronqué du jour 1 ; sur la journée entière, comparable à l'enquête, il vaut
**18,0 %**.

### Décisions de l'auteur, 2026-09-16

1. **Argument du chapitre 6** : le coût de la non-anticipation reposera sur la **mesure directe
   contre l'enquête** (le tableau ci-dessus), pas sur l'écart entre les deux lectures du
   composite. La double lecture redevient un contrôle de robustesse.
2. **Périmètre de score** : en cours d'arbitrage (voir plus bas).
3. **Quatre bras `noret`** définis et lancés le 2026-09-16.

---

## Reliquat repris du ticket 086, rejeté le 2026-09-16

Le [ticket 086](ticket_086_fidelite_de_la_regle_de_chaine_face_aux_journees_declarees.md)
« la règle de chaîne est-elle fidèle ? » a été ouvert le 2026-09-16 pendant la relecture du
chapitre 4, puis **rejeté le jour même comme doublon**. Sa mesure centrale — rejouer notre
règle sur les journées déclarées d'EMC² et compter les déplacements en voiture qu'elle aurait
interdits — est celle du § 2.3 ci-dessus, faite une heure avant son ouverture. Il citait la
« Mesure du 2026-09-16 » sans voir l'audit complet écrit en dessous.

**Les chiffres qu'il commandait existent** : 4,2 % de départs sans voiture dans l'enquête
contre 18,0 % sur la journée entière du modèle ; verrou de retour conforme à 98,5 % du
terrain ; 18,2 % contre 18,0 % de retours contraints.

**Sa dichotomie de départ est caduque.** Il opposait H1 (la règle sur-restreint : dépose,
partage du véhicule dans le ménage, retour à midi) à H2 (nos chaînes synthétiques créent plus
de conflits que la réalité). La mesure ne retient ni l'une ni l'autre : la règle est fidèle
sur ce qu'elle impose, et l'excès de blocages de sortie est une propriété du **décideur** —
il s'ordonne du prompt calibré (13,8 %) aux familles tabulaires (17,7 – 18,0 %) jusqu'au
plancher aléatoire (30,9 %), sur une seule et même cohorte. Une hypothèse sur la population
n'explique pas un écart qui varie avec le seul décideur.

### Ce qui reste valide du 086, et qui reste ouvert ici

Trois objections, qui portent sur la mesure du § 2.3 et non sur sa conclusion.

1. **La mesure réimplémente la règle au lieu de l'appeler.**
   `scripts/mesurer_enquete.py` suit le véhicule par origine/destination déclarées ; elle
   n'appelle pas les helpers partagés `_vehicle_available` / `_park_vehicles` de
   `urban_mobility_agents/vehicle_chain.py`. Elle ignore de ce fait la possession telle que le
   code la lit (elle retient « a conduit au moins une fois dans la journée » au lieu du
   fichier ménages), `_is_car_passenger`, et le seuil `RETURN_LOCK_MIN_DISTANCE_KM`. Une
   seconde implémentation mesure autre chose que ce qui tourne — objection du 086 recevable
   telle quelle.
2. **Les blocages à tort ne sont pas isolés.** On ne les lit qu'en dérivé, par
   `dont_faits_en_vp_conducteur_pct` = 13,6 % des 1 269 départs sans voiture, soit ~173
   déplacements, 0,6 % des 30 158. C'est pourtant le chiffre qui dit le plus directement ce
   que notre règle interdirait à la vraie ville ; il doit sortir en propre.
3. **Aucune ventilation par motif ni par couronne de résidence.** Les 2,4 % de journées de
   conducteur « incohérentes » au sens de notre règle se concentrent probablement sur des
   motifs identifiables — accompagnement, achats — et c'est là que se chiffrerait le coût de
   l'absence de `household_id` dans la v1 de `docs/arch/vehicle-chain.md`.

Ces trois points sont ce qui permet de chiffrer la limite du chapitre 8 depuis une mesure
plutôt que depuis une estimation. Coût : aucun appel LLM, aucune exécution relancée, lecture
seule sur les fichiers standards `Toulouse_2023_std_{depl,pers,men}.csv`. Convention
`lil-1750` : aucune microdonnée ne sort, agrégats seulement.

---

## Bras `noret` — la contrainte décomposée en ses deux règles (2026-09-16)

Quatre expériences définies et lancées le 2026-09-16 : `vehicule_chaine: true`,
`verrou_retour: false`, tout le reste identique aux bras `nosim` (même cohorte, même jeu,
mêmes graines, même artefact). `exp_{lgbm,klr,mnl,rf}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_noret_nosim`.

Elles ferment le trou de l'audit : le bras `nochn_noret` coupait les **deux** règles à la fois,
on ne pouvait pas séparer le verrou de sortie (le décideur choisit encore, dans une offre
amputée par ses propres choix antérieurs) du verrou de retour (qui ne restreint pas le choix,
il le supprime).

Composite EMD, périmètre de score actuel, cible EMC² pour la voiture : 55,9 % :

| témoin | bras | composite | hors choix unique | écart | choix forcés | part voiture |
|---|---|---:|---:|---:|---:|---:|
| lgbm | aucune chaîne | 4,21 | 4,03 | −0,17 | 30 | 56,5 |
| lgbm | **verrou de sortie seul** | **4,78** | **4,81** | **+0,02** | **68** | **50,0** |
| lgbm | chaîne complète | 4,40 | 10,04 | **+5,64** | 636 | 52,0 |
| klr | aucune chaîne | 4,22 | 3,99 | −0,23 | 30 | 58,2 |
| klr | **verrou de sortie seul** | **4,91** | **4,81** | **−0,10** | **68** | **52,2** |
| klr | chaîne complète | 4,44 | 9,51 | **+5,07** | 639 | 54,0 |
| mnl | aucune chaîne | 4,32 | 4,18 | −0,14 | 30 | 57,3 |
| mnl | **verrou de sortie seul** | **5,43** | **5,54** | **+0,10** | **66** | **51,1** |
| mnl | chaîne complète | 4,82 | 10,57 | **+5,75** | 627 | 53,1 |
| rf | aucune chaîne | 4,57 | 4,36 | −0,21 | 30 | 59,1 |
| rf | **verrou de sortie seul** | **5,66** | **5,56** | **−0,10** | **67** | **53,1** |
| rf | chaîne complète | 5,05 | 10,14 | **+5,09** | 629 | 55,0 |

Le bras `rf noret` n'est pas rejouable par la CLI (`scripts/progedo_logit/lancer_experience_rf.py`,
famille non câblée dans `decideur_modele.py` — décision assumée du 2026-09-11) : il a été joué par
son lanceur dédié depuis l'hôte, 288 s. Le résultat ne se distingue pas des trois autres.

### Trois conclusions

1. **L'écart entre les deux lectures est ENTIÈREMENT produit par le verrou de retour.** Avec la
   chaîne active mais le verrou coupé, les deux lectures coïncident (+0,02, −0,10, +0,10)
   comme elles le font sans chaîne du tout. Le mécanisme est celui identifié plus haut : le
   verrou de retour convertit 27 % des décisions en choix uniques, la seconde lecture les
   retire, et ce quart retiré est en voiture à plus de 90 %. Ce n'est pas la chaîne qui creuse
   l'écart, c'est **une règle qui supprime le choix au lieu de le restreindre**.

2. **Le coût de la myopie est isolé, et il est le verrou de sortie.** Passer de « aucune
   chaîne » à « verrou de sortie seul » coûte +0,57 (lgbm), +0,69 (klr), +1,11 (mnl) de
   composite — +1,09 pour `rf` — et **6,0 à 6,5 points de part voiture** (56,5 → 50,0 ;
   58,2 → 52,2 ; 57,3 → 51,1 ; 59,1 → 53,1). Le décideur décide encore, mais dans une offre que ses propres
   choix du matin ont amputée. C'est la mesure propre du coût de la non-anticipation, sur le
   composite cette fois, en complément du taux de blocage mesuré contre l'enquête.

3. **Le verrou de retour RAPPROCHE du terrain, il ne pénalise pas.** Ajouter le verrou au
   bras `noret` fait regagner 0,38 (lgbm), 0,47 (klr), 0,61 (mnl), 0,61 (rf) de composite et
   environ 2 points de part voiture. La précaution du § 6.1 de l'article — « le simuler en chaîne applique la
   contrainte une seconde fois, sa lecture en chaîne est donc pessimiste » — est fausse sur ce
   volet : le verrou de retour est la partie de la chaîne qui **améliore** l'accord au terrain.

Effet secondaire mesuré, qui n'était prévu nulle part : **le verrou de retour réduit d'un tiers
le nombre de sorties bloquées** (996 → 675 chez `lgbm`, 980 → 662 chez `klr`, 993 → 677 chez
`mnl`, 965 → 655 chez `rf`, journée entière). Ramener son véhicule au domicile chaque soir nettoie la chaîne ; sans
cette règle, les véhicules restent dispersés et bloquent davantage de départs ultérieurs. Les
deux règles ne sont donc pas additives, et « couper le verrou de retour » n'est pas un régime
plus permissif sur toute la ligne.

Mesure : `scripts/mesurer_bras_noret.py`, sortie `donnees/bras_noret.json`.

### Défaut constaté au passage, hors périmètre du ticket

La définition `exp_rf_…_EN_nosim` porte un **chemin de population absolu de l'hôte**
(`/Users/yvesb/…/data/population/…`) là où les trois autres témoins portent le chemin conteneur
(`/data/eqasim-output/…`). C'est une conséquence du lanceur dédié, qui réécrit ce champ à
chaque définition (`_chemin_population_hote`). L'expérience reste lançable, mais uniquement
depuis l'hôte — un lancement par la CLI du conteneur échoue sur « population introuvable ».
À signaler pour la parité revendiquée entre les quatre témoins.

---

## Correction du périmètre et rescoring (2026-09-16)

Décision de l'auteur : règle **(iii)**, les deux critères.

### Ce qui a été livré

- Spec : `specs/ticket_057/perimetre_de_score.md`, 7 règles.
- `scripts/synthesis/frames.py` — `read_moves(first_day_only="auto", horizon_jours=…)`, plus
  `couples_repetes()` (combien de couples apparaissent sur plus d'un jour) et
  `_une_occurrence_par_deplacement()` (R1/R4, le filet d'unicité).
- `services/llm-agents/experiences/score.py` — `lire_perimetre()`, **seul endroit** qui décide
  du périmètre. Les tests passent désormais par lui : c'est la duplication (`first_day_only=True`
  recopié dans deux tests) qui avait laissé une vérification reproduire un périmètre déjà
  divergent de celui du scoreur, et passer pendant ce temps. `scores_perimes()` déclare périmé
  tout score sans `lecture.coupe` — un rejeu de formule ne corrigerait rien, il recompose depuis
  des scores bruts calculés sur l'ancien périmètre.
- 9 tests neufs (`tests/test_057_perimetre_de_score.py`), sur journaux fabriqués : une exécution
  du dépôt ne peut pas produire à volonté un couple répété, et un test qui ne couvrirait que le
  cas sans répétition passerait sans rien mesurer.
- Doc : `docs/arch/score-synthesis.md` § « Périmètre commun aux trois volets », coupe n° 2.
- 25 exécutions rescorées hors ligne. **Aucun appel de modèle, aucun quota.**

### Unicité — la garantie demandée, vérifiée

Sur les 25 exécutions : 3 161 lignes de journal, 3 154 ou 3 155 lignes scorées, et **autant de
couples (personne, activité) distincts**. Zéro doublon. Les 6 ou 7 lignes d'écart sont des
`Pas de solution de déplacement`, sans décision modale par construction. La vérification ne
porte pas sur un échantillon : elle balaie toutes les exécutions scorables du dépôt.

### Ce que les chiffres deviennent

| bras | composite avant | après | hors CU avant | après |
|---|---:|---:|---:|---:|
| klr, sous chaîne | 4,44 | **3,57** | 9,51 | **5,52** |
| lgbm, sous chaîne | 4,40 | **3,63** | 10,04 | **5,87** |
| mnl, sous chaîne | 4,82 | **4,01** | 10,57 | **6,50** |
| rf, sous chaîne | 5,05 | **4,19** | 10,14 | **5,97** |
| klr, `noret` | 4,90 | **3,72** | 4,81 | **3,69** |
| lgbm, `noret` | 4,78 | **3,76** | 4,81 | **3,81** |
| mnl, `noret` | 5,43 | **4,30** | 5,54 | **4,38** |
| rf, `noret` | 5,66 | **4,39** | 5,56 | **4,34** |
| klr, hors chaîne | 4,22 | **3,66** | 3,99 | **3,46** |
| lgbm, hors chaîne | 4,20 | **3,72** | 4,03 | **3,55** |
| mnl, hors chaîne | 4,32 | **3,91** | 4,18 | **3,78** |
| rf, hors chaîne | 4,57 | **4,18** | 4,36 | **3,98** |
| `pe05` (`gemini-3.5`) | 5,00 | **4,49** | 9,41 | **5,89** |
| `pe04` (`gemini-3.5`) | 5,30 | **4,71** | 10,39 | **6,39** |
| `pe06` (`gemini-3.5`) | 5,97 | **5,37** | 11,12 | **7,30** |
| `pe05` (`gemini-3.1`) | 8,99 | **8,41** | 16,58 | **11,89** |
| `pe05` (`mistral-large`) | 8,43 | **7,20** | 16,96 | **11,51** |
| `promin02` (`gemini-3.1`) | 12,04 | **11,21** | 20,94 | **15,58** |
| `promin02` (`mistral-large`) | 15,89 | **14,29** | 27,52 | **20,09** |
| plancher durée minimale | 27,37 | **26,97** | 23,72 | **23,93** |
| plancher tout-voiture | 33,03 | **30,42** | 30,45 | **27,89** |
| plancher aléatoire | 55,85 | **50,29** | 67,81 | **57,67** |

### Analyse

**Tous les composites baissent**, et ce n'est pas un gain de qualité. Le périmètre élargi rend
au score les départs libres du matin, sur lesquels tous les décideurs font mieux que sur les
retours contraints. C'est la fin d'une pénalité que le périmètre infligeait à tout le monde —
mais **inégalement**, et c'est là que les conclusions bougent.

**Trois ordres changent.**

1. **`klr` passe devant `lgbm` sur le composite sous chaîne** : 3,57 contre 3,63, quand
   l'ancien périmètre donnait 4,44 contre 4,40. L'oracle supervisé n'a plus le meilleur
   composite EMD — la régression logistique à noyau l'a, dans les trois lectures de chaîne.
2. **L'agent calibré ne passe plus devant les quatre tabulaires hors choix unique.** `pe05`
   valait 9,41 contre 9,51 à 10,57 ; il vaut 5,89 contre 5,52 à 6,50, soit le **troisième**
   rang — à +0,02 de `lgbm`, devant `rf` et `mnl`. « Devant les quatre » devient
   « indiscernable du deuxième ».
3. **L'écart au meilleur tabulaire se creuse sur le composite** : `pe05` − `lgbm` passe de
   +0,60 à +0,86, et `pe05` − `klr` vaut +0,92.

**Ce qui tient.** Le renversement d'ordre sur les parts globales entre les deux lectures reste
vrai : L1 global sans chaîne `lgbm` 3,5 et `klr` 3,8 devant `mnl` 7,1 et `rf` 7,9 ; sous chaîne
`rf` 5,9 et `klr` 6,7 devant `mnl` 8,4 et `lgbm` 9,3. Le coût que la chaîne inflige à l'oracle
sur cet axe passe en revanche de 9,7 à **5,8** points.

Tient aussi, et se renforce, la décomposition des bras `noret` : l'écart entre les deux lectures
reste nul dès que le verrou de retour est coupé (−0,03 à +0,09 selon le témoin, contre +1,95 à
+2,49 avec lui), et le verrou de sortie seul coûte toujours entre +0,06 et +0,39 de composite
par rapport à l'absence de chaîne.

**Et l'écart entre lectures perd les deux tiers de son ampleur** partout : +5,64 → +2,24 chez
`lgbm`, +5,07 → +1,95 chez `klr`, +5,75 → +2,49 chez `mnl`, +5,09 → +1,78 chez `rf`. Le seuil
d'alarme `ECART_LECTURES_ALARME = 1,0` reste franchi par tous les bras sous chaîne : la seconde
lecture garde son sens, elle n'est simplement plus dominée par un artefact de périmètre.

### Ce qui reste ouvert

L'horodatage de `jeu.py` lui-même : le premier déplacement de la journée garde une date J+1
incohérente avec les retours du même agenda. Sans effet sur le score maintenant que la coupe ne
s'y applique plus, mais tout traitement qui trie par heure absolue s'en trouve affecté. Le
corriger impose de rejouer les exécutions, dix bras à décideur LLM compris. Décision non prise.

### Contrôle de non-régression, et ce qu'il a trouvé

`services/llm-agents/tests/` : **1 395 passés, 4 ignorés, 0 échec**.

`scripts/tests/` : 60 échecs au premier passage. Départagés en rejouant la même sélection avec
les deux fichiers modifiés mis de côté (`git stash`), à la même seconde :

- **2 régressions réelles, causées par la correction, corrigées** —
  `test_alt_prompt_replay.py::test_deux_lots_candidats_ecartent_la_decision_au_lieu_d_en_choisir_un`
  et `::test_deux_decisions_sur_un_meme_bloc_persona_sont_refusees`.
  Cause : `alt_prompt_replay.py` et `bare_prompt_replay.py` coupent le journal d'échanges par
  `if e.get("sim_day") == kept_day`, où `kept_day` vient de `stats["jour_retenu"]`. Quand la
  coupe ne s'applique plus, ce champ est absent, et le filtre comparait chaque échange à
  `None` — **il vidait l'échantillon en silence**. Les deux lignes prennent désormais la même
  forme que celle qui filtre les moves deux lignes plus haut : `if not kept_day or …`. C'est
  exactement le « deuxième point d'entrée » que `docs/arch/score-synthesis.md` signale comme
  le piège de cette coupe.
- **58 échecs préexistants, sans rapport** : 54 dans les tests du tableau de bord (l'onglet
  « 🔁 Campagne » ajouté par le ticket 074 n'est pas dans la table de `test_dashboard_onglet_url`,
  et `test_dashboard_app` échoue sur l'avertissement « aucun jeu préparé »), plus
  `test_synthese_generation_population`, `test_weather_draw`, `test_qualification_60_tickets`
  et `test_gama_includes`. Comptes identiques avec et sans la correction.

Ruff : aucun problème ajouté sur les quatre fichiers touchés (`frames.py` 17 avant / 17 après,
`score.py` 0/0, `alt_prompt_replay.py` 10/10, `bare_prompt_replay.py` 8/8).

---

## Partage de véhicule dans le ménage — chiffré, et il ne commande aucun rejeu (2026-09-16)

Alerte de l'auteur après la première formulation de l'audit : si la règle ignore la
motorisation multiple, faut-il rejouer les runs ? **Non.** Mesuré, l'effet est de
**+0,07 point de composite**, dix-huit fois sous la résolution de l'instrument (±1,3 point par
bras, ticket 080). Le détail, parce que la première formulation donnait une exposition sans son
effet et se lisait donc plus grave qu'elle n'est.

### Ce que le code fait, et ce qu'il a sous la main

`household.id` **est** dans le persona (`population.json`, à côté de `identity`), et
`number_of_cars` vaut 0, 1, 2 ou 3 — **48,7 % de la cohorte vit dans un ménage à deux voitures
ou plus**. Rien n'est perdu à la génération. C'est `vehicle_chain.py` qui n'en tient pas compte :
`_owns_car()` réduit le compte à un booléen, et `planning_vehicle_at` suit **une position par
personne et par mode**. Le modèle `Person` n'expose pas `household.id`.

### Ce que « une position par personne » veut dire — il n'y a pas de parc de véhicules

Point d'ambiguïté levé le 2026-09-16 : **le nombre de voitures n'est pas respecté, et aucune
voiture n'est attribuée à un persona**. Il n'existe nulle part de parc de véhicules par ménage,
ni de décompte, ni d'attribution. `person.state.planning_vehicle_at` est un dictionnaire
`{mode: lieu}` porté par **chaque personne**, et `_owns_car()` ne répond qu'à une question
binaire : « le ménage a-t-il au moins une voiture ? ».

Autrement dit, le modèle donne **une voiture virtuelle à chaque persona** qui réunit trois
conditions : ménage motorisé, permis, 18 ans. Trois personnes d'un ménage à une voiture en ont
donc trois, chacune la sienne, chacune garée où son propriétaire l'a laissée. C'est de là que
vient la permissivité : un couple motorisé une fois, deux permis, peut partir au travail en
voiture le matin **à deux voitures**.

Dans l'autre sens, un ménage à trois voitures dont un seul membre conduit n'en a qu'une dans le
modèle — les deux autres n'existent pas, et leur conducteur ne peut pas les prendre quand la
sienne est ailleurs.

Sur les 499 ménages de la cohorte :

| situation | ménages | personas | ce que fait le modèle |
|---|---:|---:|---|
| conducteurs ≤ voitures | 314 | 596 | correct |
| **conducteurs > voitures** | **90** | **268 (26,8 %)** | **trop permissif** — une voiture par conducteur |
| aucune voiture | 95 | 136 | correct |

Le risque structurel dominant est donc la **permissivité** — 268 personas pour lesquels le
modèle met en circulation plus de voitures que le ménage n'en déclare — pas la restriction.

### Mesuré sur l'exécution `lgbm` sous chaîne, 3 299 décisions

| biais | décisions | part |
|---|---:|---:|
| trop permissif — plus de conducteurs du ménage sur la route que de voitures | **18** | 0,55 % |
| trop restrictif — départ du domicile, sa voiture ailleurs, une autre du ménage restée là | **125** | 3,79 % |
| … dont basculeraient effectivement en voiture (mode choisi par le même décideur sur le même déplacement, offre complète) | **58** | 1,76 % |

Les 125 blocages à tort ne sont pas 125 trajets en voiture perdus : sur ces mêmes déplacements,
le même décideur en offre complète choisit la marche 45 fois, le vélo 8 fois, les transports
collectifs 14 fois. **58 seulement** vont à la voiture.

### Effet sur le composite

En substituant ces 58 décisions par celles du bras sans chaîne — même décideur, mêmes
déplacements, offre complète :

| | composite EMD | L1 global |
|---|---:|---:|
| exécution actuelle | **3,633** | 9,3 |
| avec la seconde voiture du ménage | **3,706** | 9,1 |

**+0,073 de composite** — et dans le sens défavorable, la part voiture montant à 53,2 % là où
la cible EMC² est à 55,9 % mais où la stratification, elle, se dégrade. Le L1 global gagne
0,2 point. Les deux mouvements sont sous le bruit.

Réserve, dite parce qu'elle compte : la substitution **ne propage pas l'aval** — une voiture
prise doit être ramenée, ce qui changerait les trajets suivants. C'est une estimation de
premier ordre. Elle suffit néanmoins à trancher : 58 décisions sur 3 299 ne peuvent pas, même
en cascade, produire un déplacement de l'ordre du point de composite.

### Recoupement sur l'enquête

Dans EMC² Toulouse 2023, **173 déplacements sur 30 158 (0,57 %)** sont faits en VP conducteur
alors que la voiture suivie par la chaîne était ailleurs — c'est très exactement le phénomène
« j'ai pris l'autre voiture du ménage », et il est marginal dans le terrain aussi. Deux mesures
indépendantes, même ordre de grandeur.

### Conclusion

Ce n'est pas un bug d'implémentation : `docs/arch/vehicle-chain.md` décrit exactement ce que le
code fait, et pose la limite. Ce n'est pas non plus un défaut à effet mesurable : 0,07 point de
composite. **Aucun run n'est à rejouer.** Ce qui reste utile est de porter `household.id` dans
le modèle `Person` pour une v2 de la règle — travail de modélisation, pas correction d'urgence,
et à chiffrer avec l'objection 3 du ticket 086 (ventilation par motif et par couronne).

Mesure : `scripts/mesurer_partage_vehicule.py`, sortie `donnees/partage_vehicule.json`.

### Point CLOS par l'auteur le 2026-09-16

L'effet étant mineur, le partage de véhicule dans le ménage cesse d'être instruit. Il reste une
limite à déclarer au chapitre 8, pas un chantier : ni rejeu, ni modification de
`vehicle_chain.py`, ni mesure complémentaire. Rouvrir demanderait un fait nouveau — par exemple
une ventilation du ticket 086 qui montrerait les 125 blocages à tort concentrés sur un motif
que l'article commente.


---

## État de clôture au 2026-09-16, 13 h

Inventaire demandé par l'auteur : que reste-t-il, une fois le partage de véhicule écarté ?

### Traité et clos

| élément du programme | état |
|---|---|
| § 2.1 — audit du runner et de l'application des contraintes | **clos** — une seule implémentation, 75 tests verts, invariant vérifié sur les 894 personnes |
| § 2.1 — dénominateur et renormalisation de la seconde lecture | **clos** — le mécanisme est le retrait de l'offre, quantifié bras par bras |
| § 2.1 — les ~20 % de décisions contraintes correspondent-ils au réel | **clos** — 18,0 % simulé contre 18,2 % dans EMC², sans ajustement |
| § 2.2 — contrôle sur échantillon de parcours | **clos** — porté aux 894 personnes plutôt qu'à 30, par appariement et invariant de chaîne |
| § 2.3 — validité de la règle face au terrain | **clos** — verrou de retour conforme à 98,5 % (voiture) et 93,8 % (vélo) |
| § 2.3 — la comparaison pénalise-t-elle deux fois les tabulaires | **clos** — non : sur la journée entière, la chaîne ne dégrade pas le composite, elle l'améliore sur trois témoins sur quatre |
| biais de périmètre découvert en chemin | **clos** — cause identifiée, règle (iii) implémentée, 25 exécutions rescorées, unicité vérifiée |
| séparation des deux règles de chaîne | **clos** — quatre bras `noret` joués, l'écart entre lectures vient entièrement du verrou de retour |
| partage de véhicule dans le ménage | **clos** — 0,07 point de composite, écarté par décision de l'auteur |

### Ouvert

1. **Reliquat du ticket 086 — deux objections sur trois.**
   - *Objection 1, entière* : `scripts/mesurer_enquete.py` réimplémente la règle au lieu
     d'appeler `_vehicle_available` / `_park_vehicles`. Elle ignore donc `_is_car_passenger`,
     le seuil `RETURN_LOCK_MIN_DISTANCE_KM`, et retient « a conduit au moins une fois » au lieu
     de la possession lue dans le fichier ménages.
   - *Objection 2, à moitié* : les blocages à tort ont été isolés **côté simulation**
     (125 décisions, dont 58 basculeraient en voiture). Côté **enquête**, ils restent en dérivé
     — 13,6 % des 1 269 départs sans voiture, soit ~173 déplacements, jamais sortis en propre.
   - *Objection 3, entière* : aucune ventilation par motif ni par couronne de résidence. C'est
     elle qui dirait si les blocages se concentrent sur l'accompagnement, et donc ce que coûte
     l'absence de trajet d'accompagnement généré — le chiffre que le chapitre 8 attend.

2. **L'horodatage de `jeu.py`.** Le premier déplacement de la journée garde une date J+1
   incohérente avec les retours du même agenda. **Correction du 2026-09-16, 13 h : dire « sans
   effet » était faux pour les bras à décideur LLM.** Vérifié : l'offre d'itinéraires, elle, ne
   bouge pas — le jeu sert ses propositions par `(person_id, activity_id)`, jamais par date, et
   les 808 lignes du 17 portent toutes la source `enregistree`. Mais **le bloc d'anticipation
   est daté**, lui : `_build_anticipation` appelle `day_weather_outlook(departure_time)`, et les
   deux jours diffèrent — `afternoon 12°C · evening 13°C` le 16 contre `afternoon 15°C ·
   evening 16°C` le 17. Le prompt du premier déplacement de 797 personas a donc porté **la
   météo du lendemain**, sur chacun des bras LLM.

   Deux conséquences. D'abord, l'écart est petit : trois degrés, même ciel (`Clear/Sunny`), donc
   aucune bascule pluie / pas de pluie. Ensuite, et c'est le point : **la correction du périmètre
   a fait entrer ces 797 décisions dans le score**, alors qu'elles en étaient exclues avant. Les
   composites LLM rescorés reposent donc, pour un quart de leur périmètre, sur un prompt dont une
   ligne était fausse. Les quatre témoins tabulaires ne sont pas concernés : le décideur `modele`
   ne lit jamais `ctx.anticipation`.

   **Décision de l'auteur le 2026-09-16 : corriger.** Fait — une activité qui enjambe minuit
   se reconnaît à son `start_time` postérieur à son `end_time`, le curseur recule alors d'un
   jour. Les 3 299 déplacements de la v6 tiennent désormais dans leur jour simulé, les 894 de
   rang 0 compris ; trois tests neufs, 1 408 tests de la suite au vert.

   Ce que la correction entraîne dépasse ce ticket et part au
   [ticket 088](ticket_088_jeu_corrige_et_rejeu_complet.md) : le jeu enregistré porte, pour ces
   797 déplacements, une **offre d'itinéraires calculée au mauvais jour**
   (`jeu.py:preparer()` appelle `get_itineraries(departure_time=dep.depart_ts)`), et cela
   concerne **tous** les décideurs, pas seulement les LLM. Le jeu est à re-préparer et les
   mesures à rejouer. Les trois campagnes v6 sont arrêtées.

3. **Le chapitre 6 et le § 4.4 du chapitre 4.** Signalement d'impact rendu, six points dont
   cinq majeurs. Rien n'est réécrit — c'est le verrou, et c'est conforme au quatrième critère de
   clôture. L'écriture est un travail distinct, qui demande son propre accord.

4. **Hors périmètre, signalé** : la définition `exp_rf_…_EN_nosim` porte un chemin de population
   absolu de l'hôte, là où les trois autres témoins portent le chemin conteneur. Le témoin RF
   n'est lançable que depuis l'hôte.

### Ce qui n'appartient plus à ce ticket

La filière de `number_of_cars` — d'où vient la valeur, sur quoi elle est ajustée — part au
[ticket 087](ticket_087_attribution_du_nombre_de_voitures_par_menage.md), ouvert le même jour.
Une valeur fausse ne rouvrirait pas le présent ticket : la règle de chaîne n'en lit que le signe.

### Critères de clôture — relecture

- [x] Le code appliquant les contraintes de chaîne dans le runner a été audité et validé.
- [x] L'impact de la part des décisions contraintes sur la seconde lecture est expliqué et
      quantifié — cause principale : le périmètre de score, corrigé.
- [x] L'échantillon de parcours a été inspecté, sans incohérence décelée.
- [x] Aucune affirmation péremptoire n'a été rédigée dans le chapitre 6 : signalement rendu,
      aucune écriture.
- [ ] Reliquat du ticket 086 : objections 1 et 3 entières, objection 2 à moitié.

**Un seul critère reste, et il ne porte plus sur la conclusion de l'audit** — il porte sur la
qualité de la mesure qui l'étaye côté enquête, et sur le chiffrage d'une limite du chapitre 8.


---

## Reliquat du ticket 086 — soldé le 2026-09-16

Décisions de l'auteur, les trois objections prises une par une.

### Objection 1 — la mesure réimplémente la règle : CLASSÉE, écarts assumés

`scripts/mesurer_enquete.py` suit le véhicule par origine et destination déclarées au lieu
d'appeler `_vehicle_available` / `_park_vehicles`. Quatre écarts en découlent, et ils sont
bornés :

| écart | effet sur le 98,5 % |
|---|---|
| critère de conducteur : « a conduit au moins une fois » au lieu de permis + 18 ans | le flatte — le dénominateur exclut les conducteurs qui n'ont pas roulé ce jour-là |
| `_is_car_passenger` non traité : `MODP=22` rangé dans « autre » | nul en pratique, le passager ne déplace pas le véhicule |
| seuil `RETURN_LOCK_MIN_DISTANCE_KM` ignoré : tous les retours comptés, y compris ceux de moins d'un kilomètre où la règle ne s'applique pas | le flatte |
| « même lieu » = zone fine EMC² (centaines de mètres) au lieu de coordonnées à 1e-6 degré | le dessert — sous-estime les blocages dans l'enquête |

Trois écarts sur quatre flattent le résultat, un le dessert. Aucun ne peut faire passer 98,5 %
sous 90 % : il faudrait que la moitié des retours véhiculés soient sous le seuil du kilomètre,
ou que la maille des zones fines masque un blocage sur deux. La conclusion — le verrou de
retour reproduit une régularité du terrain — tient avec cette marge, et c'est sous cette forme
qu'elle est écrite au § 4.4 du chapitre 4.

Un relecteur qui pose la question trouve ici la réponse ; la mesure n'est pas refaite.

### Objections 2 et 3 — ABANDONNÉES

Isoler les blocages à tort côté enquête, et les ventiler par motif et par couronne : écartées
par l'auteur le 2026-09-16. Le chapitre 8 garde sa limite déclarée sans chiffre associé.

### Critères de clôture — état final

- [x] Le code appliquant les contraintes de chaîne dans le runner a été audité et validé.
- [x] L'impact de la part des décisions contraintes sur la seconde lecture est expliqué et
      quantifié ; sa cause principale, le périmètre de score, est corrigée.
- [x] L'échantillon de parcours a été inspecté, sans incohérence décelée.
- [x] Aucune affirmation péremptoire n'a été rédigée dans le chapitre 6 avant la clôture :
      le signalement a été rendu, puis les chapitres 4 et 6 repris sur accord explicite.
- [x] Reliquat du ticket 086 : objection 1 classée avec ses écarts assumés, objections 2 et 3
      abandonnées.

**Les cinq critères sont remplis.** Ce que l'audit a trouvé au-delà de son programme — le
périmètre de score, et derrière lui l'horodatage du départ du matin — est corrigé ; ce que la
correction entraîne sur le substrat part au
[ticket 088](ticket_088_jeu_corrige_et_rejeu_complet.md). La filière du nombre de voitures part
au [ticket 087](ticket_087_attribution_du_nombre_de_voitures_par_menage.md).

## CLOS le 2026-09-16

Décision de l'auteur, les cinq critères remplis. Statut passé à « terminé » dans
`scripts/dashboard/tickets_status.yaml`.

Trois suites sont ouvertes ailleurs, et aucune ne rouvre celui-ci :

- [ticket 088](ticket_088_jeu_corrige_et_rejeu_complet.md) — le jeu est à re-préparer et les
  mesures à rejouer, conséquence de la correction de `jeu.py` faite ici ;
- [ticket 087](ticket_087_attribution_du_nombre_de_voitures_par_menage.md) — d'où vient
  `number_of_cars` et sur quoi il est ajusté ;
- les chapitres 4 et 6, repris le 2026-09-16 sur les scores du périmètre corrigé, seront à
  reprendre une seconde fois après le rejeu du 088.
