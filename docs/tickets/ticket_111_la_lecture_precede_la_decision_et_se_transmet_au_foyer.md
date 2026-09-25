# Ticket 111 — La lecture précède la décision, et elle se transmet au foyer

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-25 en analysant le bras traité a09 `2026-09-24_17_50`. **Plan validé
> par l'auteur le 2026-09-25, implémenté le même jour (lots 1 à 7), pas encore fusionné.**
>
> Plan : [`specs/ticket_111/plan.md`](../../specs/ticket_111/plan.md) · contrat de tests :
> [`specs/ticket_111/tests.md`](../../specs/ticket_111/tests.md) · décisions et hypothèses :
> [`specs/ticket_111/questions.md`](../../specs/ticket_111/questions.md).

---

## 1. La question, en une phrase

Un article lu au réveil doit être devant le modèle quand le lecteur décide ce jour-là, et devant
les membres du foyer à qui il en parle. Aujourd'hui il n'est ni devant l'un ni devant les autres.

## 2. Ce qui s'est passé

Expérience `a09_vent_autan` (canal `lu`, moment `reveil`), bras traité
`experiments/archive/2026-09-24_17_50`, foyer 133048 : Arthur (286920, le lecteur), sa conjointe
et deux enfants de 6 et 9 ans.

| | |
|---|---|
| Injection | 26 mars (jour 11) à 00:00:00 simulées, jugée `notable`, négative, `walking` — importance 0,30 |
| Décision du lecteur du 26/03 05:57 | produite à 20:41:22 UTC, soit vers 07:00 simulées **la veille** |
| Jugement de l'article | rendu à 20:45:42 UTC |
| Décision du 27/03 05:57 | produite à 20:46:08 UTC, **après** l'injection — sans l'article non plus |
| Entrée `[ PRESSE ]` en mémoire longue | `286920_23`, `rappels: 0` sur **tout** le run |
| Première apparition de l'article dans un prompt | 30 mars, sous forme de concept (`286920_26`, « 0 obs. ») |

Sur les onze décisions du foyer datées du 26 mars, une seule est celle du lecteur ; les dix
autres sont celles des co-résidents, qui par construction ne recevaient rien.

### 2.1 Le jour 0 était décidé la veille

L'horizon glissant tient environ un cycle d'activités d'avance : chaque trajet consommé déclenche
le calcul du trajet situé un jour plus loin. La décision du 26 mars a donc été prise le 25 au
matin, dix-sept heures simulées avant la lecture. Elle ne pouvait pas porter l'article.

### 2.2 Même décidée après, la décision ne voit pas l'article

C'est le défaut que la seule correction du calendrier aurait laissé passer. Le 27 mars, le rappel
propose 24 candidats et en sert 10, tous par le vivier sémantique : ce sont des bilans « tout
s'est bien passé ». L'article n'a aucune autre voie d'accès :

- le bloc « Ce qui a changé récemment » et le vivier C exigent une gravité d'au moins
  `memoire__importance_choc`, soit 0,70 ; l'agent a jugé l'article à 0,30 ;
- le vivier B passe par `axe_objet`, et l'entrée n'en porte pas.

Le contrat de [`evenements.md`](../arch/evenements.md) — « ce que l'agent sait en décidant : ce
qu'il a lu ce matin » — ne tient donc que si l'agent juge l'article grave. Il dépend du jugement
même que l'expérience mesure.

### 2.3 Pourquoi l'article a13 semblait être servi

Le banc a13 `2026-09-22_14_54` est servi dans 86 à 100 % des décisions (table du ticket 110). Ses
six lecteurs l'ont pourtant jugé `notable` (0,30) ou `genant` (0,50), sous le seuil. Il était
servi parce que la mémoire était presque vide : l'injection tombait aux jours 1 et 2, le rappel
comptait 1 à 9 candidats pour 10 places, et tout était servi. L'entrée de 1013072 porte
`rappels: 4`.

Le taux de service d'un article dépend donc de **l'âge de la mémoire le jour de lecture**, et non
de l'article. Une lecture tirée entre les jours 9 et 13 tombe dans une mémoire mûre qui l'enterre.

### 2.4 Un écart de documentation

`evenements.md` annonce l'injection « à 3 h simulées ». Elle a lieu au premier pas de
simulation après minuit, à 00:00 : `_injecter_evenements_du_reveil` est lancée à chaque
synchronisation, hors du bloc du point de reprise de 3 h.

## 3. Ce que l'auteur a décidé le 2026-09-25

- **La lecture est servie au lecteur quelle que soit sa gravité**, dans le bloc « Ce qui a changé
  récemment », à chaque décision et à chaque enquête d'affinité, pendant **5 jours de
  déplacement**. Le jour de lecture compte comme jour 1 ; les week-ends ne comptent pas. Ensuite,
  les règles ordinaires de la mémoire reprennent : c'est ce qu'on mesure.
- **Le lecteur transmet à sa famille.** Un appel LLM de plus par foyer : le lecteur écrit un
  message par membre, avec ses mots, ou choisit de ne rien dire. Le membre informé le reçoit en
  mémoire (`origine: entendu`), le juge lui-même, et le voit dans ses prompts pendant ses 5 jours
  de déplacement.
- **Pour un mineur, le message est la décision des parents.** Dans la réalité, ce sont les parents
  qui décident du trajet d'un enfant ; une version simplifiée de l'article ne le ferait pas
  changer. Le lecteur écrit donc ce que les parents ont décidé pour lui.
- **Le mécanisme agit au rendu du prompt**, sans toucher au pré-calcul.
- Le contrôle après run est branché sur `make report`. Pas de run de validation pour l'instant.

Écartés, avec leur raison, dans [`questions.md`](../../specs/ticket_111/questions.md) :
invalider et recalculer les décisions pré-calculées, retenir le pré-calcul, un récit identique
pour tout le foyer, le journal laissé sur la table, la conversation du dîner, le parent qui
décide à la place de l'enfant dans tous les runs.

## 4. Ce qui change

Le détail est dans le plan. En bref :

- deux clés de déclaration, `service.jours_de_deplacement` et `relais.mode` ;
- une ligne servie au prompt, tirée de la déclaration pour le lecteur et du relais pour les
  informés, qui ne dépend ni du moment où la décision est calculée ni de l'état du rappel ;
- une catégorie LLM `evenement_relais`, un appel par foyer exposé, jamais régénéré à la reprise ;
- à 00:00, l'écriture en mémoire du lecteur **et** de chaque informé, jugés chacun par eux-mêmes ;
- une trace `relais_foyer.jsonl`, qui fait foi pour savoir qui a été informé ;
- une section de `make report` qui vérifie, décision par décision, que la ligne était là.

## 5. Ce qui ne change pas

- Le pré-calcul et son horizon.
- Le régime du choc vécu (`moment: arrivee`) : il s'applique après la décision, et c'est voulu.
- Après les 5 jours, la gravité, le rappel et les concepts décident seuls.
- Aucun texte de repli : un relais invalide ne produit aucun message, avec une `[ALARME]`.
- Aucun run n'est arrêté par ce chemin.

## 6. Ce que cela change pour la mesure

- **Le témoin interne change de nature.** Dans un foyer exposé, les témoins internes sont les
  membres à qui le lecteur n'a rien dit, par son propre choix. La diffusion spontanée par la
  réflexion du soir n'est plus ce qu'on mesure dans ces foyers ; les foyers témoins restent la
  ligne de base.
- **Un enfant peut ne pas suivre la décision parentale** : il décide toujours avec son propre
  appel. C'est mesuré et rendu, pas forcé.
- **Les runs a09 déjà archivés** ne sont plus comparables sur les jours de service.
- Coût : un appel par foyer exposé, un jugement par informé, et les décisions des jours de
  service ne passent plus par le cache.

## 7. Critères d'acceptation

- [x] La première décision du lecteur le jour de lecture porte `[ PRESSE ]` dans son prompt, y
      compris quand elle a été calculée avant l'injection.
- [x] La ligne est servie pendant 5 jours de déplacement, week-ends exclus, puis cesse d'être
      garantie.
- [x] Chaque membre informé voit son message dès le jour 0 ; un mineur voit la décision de ses
      parents ; un membre non informé ne voit rien.
- [x] Un relais invalide ou refusé ne produit aucun message, et le dit.
- [x] Une exposition déclarée non avenue après un premier service lève une `[ALARME]` qui donne
      le nombre de décisions concernées.
- [x] Une décision qui doit porter une ligne n'est jamais servie depuis le cache.
- [x] À la reprise, le relais est relu, jamais régénéré.
- [x] Sans événement, ou pour un choc vécu, le bloc de mémoire est identique à celui d'avant.
- [x] `make report` rend le contrôle dans les deux sens, et signale le défaut sur
      `2026-09-24_17_50`.
- [x] `evenements.md`, `memory-stm-ltm.md`, `llm-inference.md` et le changelog sont à jour.
- [ ] Suites de tests au vert : `services/llm-agents`, `packages/mobility_llm`, `scripts/tests`.
      *(2026-09-25 : `mobility_llm` au vert ; `services/llm-agents` et `scripts/tests` sans aucun
      échec propre au ticket, comparées au commit de base dans le même worktree. Les échecs
      communs viennent des données gitignorées absentes du worktree. À recocher sur `main`, où
      elles sont présentes.)*

## 8. Voir aussi

- Ticket 100 — le canal unique, et la prise `reveil` que ce ticket rend conforme à son contrat.
- Ticket 110 — la mesure de présence au prompt, tous canaux confondus. Elle mesure ; celui-ci
  corrige le canal `lu`.
- Ticket 106 — le témoin du souvenir en mémoire longue, qui doit reconnaître `[ FOYER ]`.
- Ticket 059 — l'origine du « un lecteur par foyer » et du co-résident témoin interne.
