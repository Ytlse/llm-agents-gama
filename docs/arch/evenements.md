# Événements déclarés — un seul canal pour le vécu et le lu

> Ticket [100](../tickets/ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md).
> Plan et contrat de tests : [`specs/ticket_100/`](../../specs/ticket_100/). Cette page remplace
> `chocs-declares.md` (ticket [079](../tickets/ticket_079_chocs_declares_vecus_par_les_agents.md)),
> dont tout le contenu reste exact et se lit plus bas.

Un événement, c'est **un texte** posé dans la mémoire d'agents désignés à des jours désignés,
avec **au plus un fait mesuré**. Le reste de la mécanique est celle de la mémoire, inchangée :
gravité, force, durée de service, consolidation, croyance, contradiction.

## Les deux prises, et pourquoi la différence est le sujet

| | choc (`canal: vecu`, `moment: arrivee`) | article (`canal: lu`, `moment: reveil`) |
|---|---|---|
| Quand | à l'arrivée, **après** le choix | à 3 h simulées, **avant** le premier réveil |
| Ce qui change dans le monde | un retard chiffré | **rien** |
| Ce que l'agent sait en décidant | l'offre nominale, rien d'autre | ce qu'il a lu ce matin |
| Écriture en mémoire | texte **joint** à l'observation d'arrivée, courte seulement | entrée **autonome**, courte **et longue** |
| Jugement | **à l'injection**, attendu | à l'injection |
| Texte | écrit par nous, jour par jour | **cité**, un seul, avec son empreinte |
| Qui | `mode`, `tirage`, `agents` | `foyers` — un lecteur par ménage |
| Quel jour | déclaré, le même pour tous | **tiré par foyer** dans une fenêtre |

Le jour du choc **ne mesure aucun choix** : tout l'effet des jours suivants est imputable au
souvenir, et à rien d'autre. Le jour de l'article n'en mesure **que**. C'est ce contraste que le
chapitre 7 mesure, et il n'existe que si les deux prises restent à leur place.

⚠ **L'article écrit AUSSI en mémoire longue, et le choc non.** Ce n'est pas un oubli, c'est le
régime : une décision ne lit que la mémoire longue, et la consolidation du soir consomme le
tampon court sans y déverser le texte brut. Un article posé en mémoire courte ne serait vu par
aucune décision de la journée — « l'agent sait avant de décider » serait faux. Pour le choc, au
contraire, un effet qui ne commence que le lendemain est exactement ce qu'on veut. Ce qui reste
commun aux deux canaux est la **qualification**, pas le chemin d'écriture.

## Lancer

```bash
make run EVENEMENT=c6_voiture_suspecte
make run EVENEMENT=a13_punaises_metro
```

`CHOC=` et `PRESSE=` sont des alias du même levier, et la commande dit lequel a servi.
`EVENEMENT=0` retire la déclaration.

**Le cache de décisions se coupe tout seul les jours d'événement** (décision de l'auteur,
2026-09-22). Plus rien à penser au lancement. ⚠ La coupure porte sur le **jour** de l'événement,
pas sur la fenêtre d'**après**, qui est celle qu'on mesure : la clé exacte du cache ne porte ni
la date ni la mémoire, et seule la branche sémantique (0,95 de similarité) l'en empêche — ce que
personne n'a mesuré. Le journal compte, jour par jour de la fenêtre, combien de décisions y ont
été servies depuis le cache. `CACHE=0` lève entièrement la réserve.

## Le jugement de l'agent

Depuis le ticket 100, l'agent **juge** ce qu'il vient de vivre ou de lire, sur les cinq échelons
ancrés de `llm/gravite.py`. Et depuis la décision **D7 du 2026-09-22**, la gravité d'une entrée
est cette estimation **et elle seule**, dans les deux canaux.

⚠ **Il n'y a plus de plancher.** La règle `max(estimée, mesurée)` existait pour qu'un modèle qui
juge « anodin » un dépannage de trente minutes ne puisse pas le dégrader. Elle est levée : ce
dépannage vaut maintenant 0,10, et son souvenir vit 2,8 jours au lieu de 15,4.

Ce qui la remplace ne corrige rien. L'écart `estimée − mesurée` est journalisé à chaque
jugement, écrit dans `evenements.jsonl` sous `ecart_au_fait`, et une `[ALARME]` se lève quand
l'agent sous-estime de plus d'un échelon. On veut savoir, pas rattraper : corriger en silence
rétablirait le plancher sous un autre nom, et la campagne mesurerait la garde au lieu de l'agent.

Le retard reste **subi** pour autant : il décale la journée, contraint les trajets suivants, et
entre dans ce que l'agent raconte le soir. Il cesse seulement de peser sur la gravité. Et
`jugement: aucun` devient le seul chemin par lequel la gravité déterministe qualifie une entrée.

### Un départ reporté n'est pas un retard subi

`expected_arrive_at` est calculé par GAMA depuis le `schedule_at` **d'origine**, et il n'est pas
recalculé quand le départ est reporté — ni par le bouclage J+1 (`departure_time += 86400`), ni
par la règle `agent.no_weekend_departures`. Le retard d'arrivée valait donc le report tout
entier :

    schedule_at vendredi 19:35 · started_at lundi 19:15 · attendu vendredi 19:50
    arrivé lundi 19:27  →  71,6 h de « retard »  pour un trajet de douze minutes

Ce trajet est arrivé **en avance sur son propre départ** : douze minutes contre quinze
planifiées. Il produisait pourtant une gravité de 0,70 et un souvenir « grave » — contre 0,75
pour un choc c3 déclaré. Une ligne de base ainsi peuplée ne se distingue plus de ce qu'on y
injecte, et le prompt de l'agent portait un `Late by: 23 hours` qu'il n'avait pas vécu.

`retard_d_arrivee()` (`text_helper/models/arrival.py`) retire le report. Il le **déduit** :
`started_at - schedule_at` au-delà d'une demi-journée ne peut être qu'un report de calendrier,
les deux règles déplaçant un départ d'un jour entier ou jusqu'au lundi, là où un glissement
ordinaire se compte en minutes.

⚠ **Ce qui reste compté**, et doit le rester : un départ qui glisse de vingt minutes parce que
l'activité précédente a débordé. C'est un retard vécu. Seul le report décidé par le calendrier
est retiré ; `departure_delay_s` de `gama_arrivals.csv` porte le glissement ordinaire pour qui
veut le lire à part.

### Le jugement est ATTENDU, il ne part pas en tâche de fond

Le ticket 100 le posait « dans la file du soir » : l'appel partait en arrière-plan et relevait
l'importance de l'entrée courte avant que la consolidation la consomme. Le raisonnement
supposait une consolidation **du soir**. Il n'y en a pas : la réflexion part au **seuil
d'entrées** (`stm_reflection_min_entries`, 10 par défaut), à l'heure où le compte est atteint.

L'entrée d'un événement est donc souvent celle qui fait franchir ce seuil — elle déclenche la
consolidation qui la consomme, pendant que son propre jugement est encore en vol. Mesuré le
2026-09-23 : injection à 10:24:08, consolidation à 10:24:09, jugement rendu à 10:24:14. Cinq
secondes trop tard, et l'événement qualifié sur le fait mesuré (0,87) au lieu de la gravité
jugée (0,75) — c'est-à-dire sous le régime que D7 a abandonné.

La course n'est pas gagnable : elle se joue sur le nombre de trajets qui précèdent l'événement
dans la journée, et le jugement la perd chaque fois que l'entrée injectée est la dixième. Il est
donc **attendu**. Le traitement de cette arrivée-là prend quelques secondes de plus, une à deux
fois par run.

L'`[ALARME]` du jugement tardif **reste en place**. Elle ne peut plus se déclencher, et c'est
exactement pourquoi on la garde : quiconque reviendrait au différé retrouverait l'alarme plutôt
qu'un silence.

Un échelon hors grille est **refusé**, avec `[ALARME]`, et l'exposition est déclarée non avenue.
Aucun repli, aucune valeur médiane : un repli fabriquerait une exposition non jugée et la
compterait comme les autres.

`jugement: aucun` est l'**ablation déclarée** — c'est sous elle que tourne le test en or de la
migration. Un `canal: lu` sans jugement n'arme pas un run : l'article entrerait à gravité 0,00,
donc pour 2,8 jours, et son silence passerait pour une absence d'effet.

## Ce que le foyer en fait

Derrière `memoire__partage_foyer_enabled`, **faux par défaut**. À la consolidation du soir, ce
que les autres membres présents du ménage ont vécu et appris entre dans l'appel **comme une
entrée de plus** — pas un appel LLM de plus.

Deux choses circulent, et **un seul saut** :

- **le bilan du soir** — la réflexion que l'autre a lui-même écrite, **citée**, jamais
  reformulée. Un récit n'est jamais copié dans la mémoire du receveur : il n'existe que dans
  l'appel, donc il n'y a rien à re-raconter ;
- **les croyances** — les concepts, sous les six règles du ticket 078. Une croyance née d'un
  ouï-dire porte `origine: entendu` et ne repart **jamais**, même confirmée plus tard.

Quatre gardes contre la boucle : le repère par receveur (jamais deux fois la même chose),
`known_beliefs` dans le prompt (c'est là que l'agent reconnaît ce qu'il sait déjà), la
provenance, et un détecteur de reformulation circulaire qui **alerte sans jamais couper**.

### Jouer une expérience de foyers depuis l'onglet 🧠 Expériences Mémoire

L'onglet (ticket 109) et `make experience-memoire-lancer EXP=…` acceptent une **population
scellée** comme `population_20_foyers_059`, en plus d'un persona unitaire. Ce qui change alors :

- **L'exposition déclarée est gardée telle quelle.** Sur un persona seul, la règle est forcée à
  `agents` et restreinte à lui. Sur un jeu de plusieurs agents, seules `foyers` et `agents` sont
  admises : une règle `mode` ou un tirage est **refusé** avant le lancement, parce que la
  réécrire désignerait le nom de la population comme un habitant — et personne ne serait exposé.
  Une règle `agents` dont aucun identifiant n'est dans la population est refusée pour la même
  raison.
- **Une population introuvable arrête tout.** Un nom qui n'est ni un dossier de
  `data/population/` ni un identifiant numérique lève `[ALARME] [population]`. Seul un
  identifiant numérique garde le repli historique `population_1_<id>`.
- **Le partage dans le foyer se coche dans le formulaire** (`partage_foyer: true` dans
  `experience_memoire.yaml`, suffixe `_foyer` dans le nom). L'orchestrateur pose
  `MEMOIRE__PARTAGE_FOYER_ENABLED` — **à vrai comme à faux** — et le lanceur le retrouve dans
  `identite_run.json` (champ `partage_foyer`) : un conteneur qui ne l'aurait pas reçu arrête le
  bras. Coché sur une population sans foyer d'au moins deux membres, l'expérience est refusée :
  elle tournerait sans rien partager et se lirait « rien ne se transmet ».
- **L'horizon est celui de l'expérience**, et non plus 42 jours en dur ; le délai de garde du bras
  suit le volume (90 s par agent et par jour simulé, jamais moins de 6 h).
- **Le fournisseur peut être imposé** (`adaptateur: groq`). Un même nom de modèle peut être servi
  par deux fournisseurs — Groq et LM Studio servent tous deux `qwen/qwen3.8-27b` — et sans ce
  filtre une partie des appels partirait ailleurs. Un modèle qu'aucune instance du fournisseur ne
  sert fait refuser le bras.
- **« Bras à jouer »** : `A — traité seul (debug)` laisse l'expérience à l'état `traite_ok`,
  jamais `terminee` — un bras seul ne passe pas pour une mesure A/B. L'état final se lit sur les
  **bras**, pas sur l'invocation : un témoin joué seul après un traité abouti termine l'A/B.
- **Un bras coupé par le garde-fou (ticket 105) est SUSPENDU, pas réussi.** Quota journalier ou
  replis consécutifs : le contrôleur pose `en_attente_quota.json` puis s'arrête en code 0. La
  cohorte relit ce marqueur (s'il date de ce bras), écrit `reprise.json` dans le dossier du bras
  (nom du run à reprendre) et rend le code 7. L'orchestrateur marque le bras `suspendu`,
  l'expérience `suspendue` (badge ⏸ dans l'onglet), et **ne lance pas le témoin** sur un quota
  vide. Relancer la même expérience (bouton « ⏯ Reprendre le bras suspendu ») reprend le bras
  par son nom (`make run … REPRISE=<run>`, ticket 091) ; un bras déjà `ok` n'est jamais rejoué.
- **Les foyers exposés viennent du MANIFEST quand la déclaration vise une autre population.**
  `a09_vent_autan` déclare les six foyers de `population_20_foyers_059` : sur une autre
  population, aucun ne serait présent et personne ne lirait. La cohorte prend alors
  `groupes.expose` du `MANIFEST.yaml` de la population, et refuse le bras s'il n'y en a pas.
- **Le contrôle d'injections (ticket 108) compte un lecteur par foyer exposé**
  (`foyers × lecteurs_par_foyer`), sur l'événement DÉRIVÉ réellement joué ; un écart lève
  `[ALARME] [108]` en fin d'expérience.
- **L'essai à blanc (`DRY_RUN=1`) ne touche ni à l'état ni aux bras** (2026-09-24). Il vérifie le
  routage des modèles et le refus du partage sans foyer, sans simulation ni appel, et range ses
  traces synthétiques sous `essai_a_blanc/`. Jusque-là il écrivait `etat.json` et un faux
  `moves.csv` dans `traite/` et `temoin/` : le c6 s'affichait « Terminée » après 50 ms, et une
  vraie relance aurait sauté les deux bras.
- **Enchaîner plusieurs expériences sans surveillance :** `make experience-memoire-nuit` joue,
  une par une et en arrière-plan, toutes les expériences déclarées non terminées, dans l'ordre de
  création, ou `EXP="a b c"` dans cet ordre. Un bras suspendu pour saturation (503) est relancé
  toutes les 30 min (`ATTENTE_S`), au plus 6 fois sans jour simulé gagné (`ESSAIS_MAX`). Un quota
  épuisé fait passer à l'expérience suivante. La commande refuse de partir si une campagne tourne
  déjà et empêche la mise en veille du Mac (`caffeinate`). Le journal
  `experiments/enchainement_nuit_<date>.log` se termine par un bilan : terminées, suspendues à
  relancer, en échec.

**Les jours 13 et 14 sont un week-end.** Le run démarre le lundi 16 mars 2026 ; le jour 12 est
un vendredi, et le dépôt tourne sous `NO_WEEKEND_DEPARTURES` : aucun départ le week-end, pour
aucun agent. c1 (jours 12 à 14), c2 et c3 (12 et 13) ne s'appliquent donc qu'au jour 12, et
l'`[ALARME] [108]` le dira en fin d'expérience. Le jour 12, 861500 ne prend que la voiture et
les transports collectifs (bras c3 du 24/09) : **c4 (train) et c5 (marche, vélo, deux-roues) ne
l'exposeraient pas**. Il leur faut un persona qui emprunte ces modes ce jour-là.

**Seuls les adultes lisent l'article** (2026-09-24). Le tirage des lecteurs d'un foyer
(`lecteurs_par_foyer`) se fait parmi ses membres mobiles d'au moins 18 ans : dans une famille de
quatre à deux adultes, un lecteur est tiré parmi les deux parents ; l'autre parent et les enfants
sont les témoins internes. Un âge absent n'exclut pas (il est signalé en WARNING) ; un foyer
exposé sans adulte mobile lève `[ALARME]` et n'a pas de lecteur.

Population de mise au point : `population_4_foyer_133048` — un foyer de quatre (Arthur, 40 ans,
et sa conjointe, 42 ans, cyclistes réguliers qui prennent aussi voiture, TC et marche ; deux
enfants de 6 et 9 ans, surtout conduits). Extraite par
`extraire_foyers.py --taille 4 --adultes 2 --menage 133048 --temoins 0 --motif …` ; le motif est
écrit au manifeste.

Répartition Gemini par défaut (2026-09-24), mesurée sur 861500 (111 agents-jours) :

| Fonction | Part des requêtes | Modèle |
|---|---|---|
| Réflexion du soir (STM) | 49 % | `gemini-3.5-flash-lite` |
| Décision | 43 % | `gemini-3.1-flash-lite` |
| Enquête d'affinité | 5 % | `gemini-3.1-flash-lite` |
| Auto-réflexion (LTM) | 3 % | `gemini-3.1-flash-lite` |
| Jugement de l'article | < 1 % | `gemini-3.1-flash-lite` |

Configuration de debug du 2026-09-24, tout Groq (hors quota Gemini) :

| Fonction | Modèle | Pourquoi |
|---|---|---|
| Décision | `openai/gpt-oss-120b` | le plus gros volume ; modèle *Production*, sans plafond de sortie |
| Jugement de l'article | `qwen/qwen3.8-27b` | 6 appels courts, du J9 au J13 : le seul rôle qui tient sous 1 000 tokens de sortie/min |
| Réflexion du soir, auto-réflexion, enquête | `openai/gpt-oss-20b` | ~26 appels par jour simulé, plus le jalon du J12 |

⚠ Le quota de `gpt-oss-120b` (1 000 requêtes/jour) couvre une quinzaine de jours simulés pour
vingt agents : au-delà, le garde-fou du ticket 105 coupe le bras.

## Ce qui se mesure

| Sortie | Contenu |
|---|---|
| `evenements.jsonl` | une ligne **par exposition**, jamais deux : canal, moment, jour relatif, rôle, retard injecté, et ce que l'agent en a dit — intensité, valence, modes, importance estimée **et** retenue |
| `moves.csv` | `Rôle` et `Raison d'exposition`, à côté de `Choc` et `Jour relatif au choc`, qui gardent leur nom du 079 |
| `mesures/evenement_par_jour.csv` | une seule table pour les deux régimes, avec la colonne `canal` |
| `scripts/analysis/figure_evenement.py` | **une seule figure** : décrochage et retour par rôle, en jour relatif. La figure 7.2 en est la première instance |
| `scripts/analysis/tableau_quatre_voies.py` | par quelle voie le passé a atteint la décision, par régime et par rôle |

**Les trois rôles ne se déduisent pas l'un de l'autre.** `expose` a rencontré l'événement ;
`co_resident` vit sous le même toit et n'a **rien** reçu — c'est chez lui que se lit ce qui se
transmet ; `temoin` ni l'un ni l'autre. Une colonne vide n'est pas un rôle : elle dit que le
dispositif ne sait pas encore qui lit.

**La garde de vacuité est écrite sur la figure.** Un rôle dont l'effectif tombe sous le minimum
déclaré sort « non concluant » **écrit sur l'image**, jamais une série absente : une série qui
manque se lit comme un effet nul par celui qui ne sait pas qu'elle manque.

### Les quatre voies, et ce que le tableau ne sait pas faire

Le § 3.4 du manuscrit nomme quatre chemins par lesquels le passé atteint une décision : « Mes
habitudes », « Ce que je sais », « Ce qui a changé récemment », et les trois souvenirs du rappel
vectoriel. Le tableau dit par laquelle l'événement est passé.

⚠ **L'appariement par le texte échoue pour le vécu**, et le tableau le dit au lieu de le taire.
Mesuré le 2026-09-16 : le texte injecté n'est jamais recopié tel quel — la réflexion du soir le
reformule, et c'est la reformulation qui atteint la mémoire longue. Deux recherches, donc : la
littérale, fiable quand elle trouve ; et celle par mots saillants, **indicative**, marquée `~`.
Une décision pour laquelle aucune ne conclut sort **vide**, et le rendu compte ces décisions
muettes en toutes lettres. Pour le canal `lu`, l'attribution se fait sur `agent_id=` dans le
prompt : tous les lecteurs d'un même article partagent le même texte, chercher le texte seul ne
dirait pas qui l'a vu.

---

---

> Ticket [079](../tickets/ticket_079_chocs_declares_vecus_par_les_agents.md). Contrat de test :
> [`specs/ticket_079/tests.md`](../../specs/ticket_079/tests.md). Livré le 2026-09-15 ; 36 tests
> collectés, qui tournent inchangés contre le paquet neuf.

Un choc, c'est **un retard chiffré** plus **une phrase vécue**, posés sur des agents désignés à des
jours désignés, avec une intensité déclarée jour par jour.

```
  Déclaration (YAML)                Exécution (contrôleur)              Trace
 ┌─────────────────────┐          ┌──────────────────────────┐     ┌──────────────────┐
 │ qui  : mode vélo    │          │ à l'arrivée de l'agent : │     │ qui a été touché │
 │ quand: jour 12      │  ──────► │  + retard   35 min       │ ──► │ combien de retard│
 │ quoi : +35 min      │          │  + phrase   « I got a…»  │     │ quelle phrase    │
 │ mots : « flat tyre »│          │  + gravité  incident=oui │     │ quelle gravité   │
 └─────────────────────┘          └──────────────────────────┘     └──────────────────┘
```

## Lancer

```bash
make run OFFLINE=1 CACHE=0 CHOC=c3_panne_reseau
make run OFFLINE=1 CHOC=0          # retirer le choc
```

Les cas livrés sont dans [`services/llm-agents/config/evenements/`](../../services/llm-agents/config/evenements/) :
`c1_bouchon_rocade`, `c2_crevaison`, `c3_panne_reseau`, `c4_train_supprime`, `c5_orage_grele`,
`c6_voiture_suspecte`. Ils couvrent les six modes du dépôt. Les copies de `config/chocs/` sont
l'ancien format du ticket 079, lues seulement quand `config/evenements/` n'a pas le fichier.
Depuis le 2026-09-24, les six déclarent `cadence: jour` (voir « Cadence »), dans les deux répertoires.

⚠ **Coupez le cache.** Sa clé ne porte aucune durée : une décision prise avant le choc peut être
resservie pendant. Une `[ALARME]` se lève si on l'oublie, mais elle ne corrige rien.

## Le régime subi, et pourquoi c'est le bon

L'agent décide **en voyant l'offre nominale**, puis encaisse. Aucun moteur d'itinéraire n'est
sollicité : ni OTP, ni OSMnx, ni GTFS. Un test de frontière le vérifie sur les imports du module.

Ce n'est pas qu'une économie. **Le jour du choc ne mesure alors aucun choix**, et tout l'effet
observé les jours suivants est imputable au souvenir, à rien d'autre. Un choc qui dégraderait aussi
l'offre mêlerait inextricablement l'adaptation à la contrainte et l'inertie de la mémoire — ce que
l'Étape 3a cherche précisément à séparer.

| | Choc subi (livré) | Choc anticipé (autre ticket) |
|---|---|---|
| L'agent sait, en décidant | rien | l'offre est dégradée sous ses yeux |
| Ce qu'on mesure | l'hystérésis pure | l'adaptation sous contrainte |
| Exemples | bouchon, crevaison, orage, panne soudaine | grève annoncée, travaux, fermeture |

⚠ **À déclarer dans l'article.** Le manuscrit (§ 5.3) exige que l'événement soit « le même
événement déclaré deux fois, une fois en langue et une fois en graphe ». Le régime subi ne le
déclare **qu'une fois**, en langue. C'est légitime pour un imprévu — personne ne connaît la panne
avant de la subir — mais cela doit être écrit, pas laissé implicite.

## Ce qui se passe dans la mémoire

Le ticket 071 avait câblé la gravité de bout en bout en laissant `incident_reseau` (poids 0,20) sans
source, avec le commentaire « il n'y a qu'une source à brancher le jour venu ». **Le choc est cette
source.** Une fois le retard ajouté et la composante portée, tout le reste suit sans une ligne :

Valeurs **calculées depuis les déclarations**, jamais recopiées d'un run :

| Choc | Retard | Gravité (avant le 21/09) | Gravité | Durée de vie | Servi dans le bloc |
|---|---|---:|---:|---:|---|
| Trajet banal | 0 | 0,00 | 0,00 | 2,8 j | non |
| Bouchon (c1, jour 3) | 12 min | 0,40 | 0,40 | 9,5 j | non |
| Orage (c5) | 15 min | 0,45 | 0,45 | 10,4 j | non |
| Moteur (c6, jour 2) · Panne réseau (c3, jour 2) | 20 min | 0,53 | 0,53 | 11,8 j | non |
| Bouchon (c1, jour 2) | 25 min | 0,62 | 0,62 | 13,2 j | non |
| **Moteur (c6, jour 1)** | 30 min | 0,70 | **0,70** | 14,6 j | **15,3 j** |
| **Crevaison (c2)** | 35 min | 0,70 | **0,77** | 15,7 j | **16,5 j** |
| **Train supprimé (c4)** | 50 min | 0,70 | **0,86** | 17,3 j | **18,2 j** |
| **Bouchon (c1, jour 1)** | 60 min | 0,70 | **0,88** | 17,6 j | **18,5 j** |
| **Panne réseau (c3)** | 45 min + corresp. ratée | 0,90 | **1,00** | 19,6 j | **20,6 j** |

## Le retard ne sature plus (ticket 095, 2026-09-21)

**Avant**, la composante de retard faisait palier à 30 minutes. Déclarer 45, 60 ou 90 minutes
donnait rigoureusement la même gravité : quatre chocs du catalogue — la crevaison, le train, le
bouchon du premier jour et le moteur — étaient **le même événement** pour la mémoire, alors que
leurs retards vont de 30 à 60 minutes. Un profil décroissant resté au-dessus de 30 minutes
n'existait que dans le texte.

**Maintenant**, la composante monte encore au-dessus de la référence, en décélérant, vers un
maximum de 0,70 qu'elle n'atteint jamais :

```
t ≤ 30 min :  0,50 × t / 30 min                     ← rigoureusement inchangé
t > 30 min :  0,70 − 0,20 × exp(−(t − 30 min) / 12 min)
```

**En dessous de trente minutes, rien n'a bougé d'un millième** — c'est ce qui rend le changement
sûr, les trois quarts du catalogue étant dans ce cas. La constante de temps du prolongement est
calée pour que la **pente** soit continue au point d'ancrage : sans cela, une seconde de plus que
la référence vaudrait un saut de gravité.

⚠ **Pourquoi pas simplement retirer le palier.** Une composante linéaire non bornée atteindrait
1,0 dès soixante minutes, la gravité totale étant bornée à 1 : soixante, quatre-vingt-dix et cent
vingt minutes redeviendraient indiscernables, et les trois autres composantes cesseraient de peser
quoi que ce soit. Le mur serait déplacé, pas supprimé.

⚠ **Deux conséquences à connaître.** La somme des quatre maxima vaut désormais 1,20 et non plus
1,00 : le bornage à 1 mord pour la combinaison extrême, et c'est le cas de la panne réseau (c3),
seul choc du catalogue à saturer l'échelle. Et le cumul de gravité d'une journée monte avec les
retards longs, donc la réflexion de rupture se déclenche un peu plus souvent.

Le mode d'avant reste déclarable — `MEMOIRE__RETARD_SATURATION=palier` — pour reproduire un run
antérieur au 21 septembre 2026.

Au-delà de **0,70**, le souvenir entre au **vivier des chocs** : il est repêché à chaque décision
**sans aucune condition** de lieu, d'heure ni de motif. C'est le mécanisme qui porte l'hystérésis.

**Tous les cas ne le franchissent pas, et c'est voulu.** L'orage (0,45) et le troisième jour de
bouchon (0,37) restent en deçà : leur souvenir vit trois à quatre fois plus longtemps qu'un trajet
banal, mais il est rappelé par le **vivier par objet** — quand le mode concerné est proposé — et non
hors contexte. La gradation est l'information : un orage n'est pas une panne de réseau, et le
dispositif doit le refléter plutôt que de tout porter au même rang.

## Un `vecu` raconte, il ne commande pas

Un texte qui s'adresse à l'agent ou lui dicte une conduite est **refusé au chargement**.

| Admis | Refusé |
|---|---|
| « I was stuck for a solid hour on the ring road » | « avoid the ring road tomorrow » |
| « Flat tyre, hands covered in grease » | « you should take the metro instead » |

**Il ne conclut pas non plus, et il n'annonce rien** (2026-09-19). La première version de la règle
ne refusait que l'adresse à la **deuxième** personne. Elle laissait passer le même biais écrit à
la première : un verdict sur un mode, ou une intention pour demain.

| Famille | Admis | Refusé |
|---|---|---|
| **Verdict** — une croyance durable sur un mode | « the engine stalled twice on the way » | « I no longer trust this car », « this bus line is unreliable » |
| **Intention** — ce que l'agent fera | « I had to sort out another way of getting around » (fait passé) | « I am thinking about not using this car anymore », « from now on I will take the metro » |
| **Doute** — ni l'un ni l'autre | « I am starting to wonder whether this is worth it » | — |

La croyance est exactement ce que l'étape de réflexion existe pour **produire**. L'écrire dans le
`vecu` court-circuite le seul mécanisme que l'expérience prétend mesurer, et le résultat se lit
comme un apprentissage alors qu'il n'est qu'une reformulation.

⚠ **Mesuré sur le run du 2026-09-19.** `vecu` : *« I no longer trust this car at all »*. Réflexion
nocturne produite le soir même : *« consider alternative transport options »*. Cette phrase a été
servie à chacune des quarante décisions des quatorze jours suivants, et la part modale de la
voiture est passée de 80 % à 0 % du jour au lendemain. On ne mesurait plus un agent qui apprend,
mais un modèle qui ne se contredit pas.

La limite basse est volontairement placée sur le **doute** : les cinq chocs c1 à c5 passaient déjà
la règle sans modification — elle rend vérifiable une pratique existante, elle ne la condamne pas.

Le refus est franc et non un avertissement : un avertissement au milieu d'un journal de run
n'alerte personne — le ticket 077 l'a mesuré, deux WARNING noyés dans 355 000 lignes ont laissé le
mécanisme des concepts cassé trente jours. Et une consigne qui passe ne biaise pas un peu : elle
fabrique exactement le résultat qu'on prétend mesurer.

Les textes livrés sont **en anglais**, langue du dispositif depuis le ticket 074. Le format n'impose
aucune langue ; les exemples si.

## Ce qui est enregistré

| Où | Quoi |
|---|---|
| `moves.csv` | `Choc`, `Jour relatif au choc` — pour **toute** décision, y compris les jours nominaux : c'est l'abscisse des courbes d'hystérésis, et une abscisse qui n'existerait que les jours de choc ne tracerait rien |
| `gama_arrivals.csv` | `retard_injecte_s`, **à côté** de `delay_s` |
| `chocs.jsonl` | une ligne par application : agent, instant, jour du run, jour relatif, raison de l'exposition, retard, incident, correspondance, texte vécu, gravité obtenue et son détail par composante |
| `choc.yaml` (dans le run) | la déclaration intégrale, pour relire un résultat sans le dépôt |
| journal | compteurs de fin de journée **même à zéro** : exposés, épargnés, retard total |

**La règle qui ne se négocie pas :** le retard **injecté** et le retard **mesuré** ne se confondent
jamais. Deux variables, deux colonnes, deux champs. La gravité utilise la somme ; les traces
gardent les deux. Sans cette séparation, aucune relecture ne pourrait plus distinguer ce que la
simulation a produit de ce qu'on lui a fait dire.

## Exposition

| Règle | Qui est touché | Pour |
|---|---|---|
| `mode` | les agents dont le trajet qui arrive a été fait dans l'un des modes déclarés | chocs collectifs (c1, c3, c4, c5) |
| `tirage` | une part, tirée de façon **déterministe** et stable d'un run à l'autre | chocs individuels (c2) — les non tirés sont le **témoin interne** |
| `agents` | des identifiants nommés | reproduire un cas précis |

⚠ **`agents` et `modes` se conjuguent** (2026-09-15). Déclarer les deux restreint les agents
nommés à leurs trajets faits dans ces modes. Auparavant `modes` était lu, validé, puis **ignoré**
par cette règle : un incident de voiture posé sur un agent multimodal lui faisait lire « the
engine made a grinding noise » au retour d'un trajet en bus, et sa mémoire enregistrait une
histoire impossible. Sans `modes`, le comportement ne change pas : l'agent nommé est exposé quel
que soit son mode.

Le tirage est une empreinte de `(graine, choc, agent)` : il ne dépend ni de l'ordre d'arrivée des
observations, ni du nombre d'agents. Deux rejeux du même scénario touchent exactement les mêmes.

## Cadence

Combien de fois par journée un agent exposé subit-il le choc ?

| `cadence` | Effet | Pour |
|---|---|---|
| `trajet` (défaut) | chaque arrivée éligible le subit | un bouchon, une panne de réseau — l'état du monde dure toute la journée |
| `jour` | seule la **première** arrivée éligible de la journée le subit | une panne réparée, une crevaison — l'incident est ponctuel |

Le défaut est `trajet`, comportement historique ; il est **journalisé au chargement** pour qu'un
fichier muet ne change jamais de comportement en silence. Une valeur inconnue est refusée, comme
une règle d'exposition inconnue.

⚠ **Pourquoi ce réglage existe.** Au run du 2026-09-19, c6 déclarait une panne avec dépannage de
trente minutes, et l'agent faisait quatre trajets en voiture ce jour-là : `chocs.jsonl` porte
**quatre** applications, quatre dépannages, quatre fois le même récit. Le protocole en comptait
un. L'intensité réelle valait quatre fois l'intensité annoncée, et rien ne le disait.

**Les six chocs livrés déclarent `cadence: jour`** (c3 et c6 depuis le 23/09, c1, c2, c4 et c5
depuis le 2026-09-24). Le texte de chaque jour raconte **un** trajet et porte **un** retard
(« arrived 60 minutes after the time I had planned ») : en `trajet`, ce même retard de soixante
minutes frappait chaque trajet en voiture de la journée. Un bouchon qui dure vraiment toute la
journée se déclarerait en `trajet` avec un texte écrit pour être revécu à chaque trajet.

Les arrivées non touchées parce que l'agent l'avait déjà été le jour même sont comptées **à
part** dans le journal : ni exposées, ni épargnées. Les confondre ferait passer un choc appliqué
une fois pour un choc qui rate trois trajets sur quatre.

## Une journée de choc sans exposé est une alarme

Une journée déclarée dans `jours` et close avec zéro exposé est un protocole qui **n'a pas eu
lieu**. Elle lève une `[ALARME]` en ERROR, et l'analyse ne doit pas la compter comme une journée
de choc.

⚠ Le second choc de c6 (jour 16) est dans ce cas : l'exposition est restreinte aux trajets en
voiture, et l'agent n'en faisait plus. Un choc de renforcement ne peut frapper que ceux qui n'ont
pas déjà réagi. Le journal le disait en INFO, personne ne l'a lu, et le rapport du run a continué
d'annoncer deux jours de choc et une « phase péri-choc J15–J16 » qui n'existe pas.

**`chocs.jsonl` fait foi, jamais le fichier de déclaration** : le premier dit ce qui a eu lieu,
le second ce qui était prévu.

## Limites connues

1. **Un seul choc à la fois**, volontairement : deux chocs superposés rendraient l'attribution
   impossible, et le mécanisme ne doit pas fabriquer la confusion qu'il sert à lever.
2. **`c2` ne rend pas le vélo réellement indisponible** le lendemain : seul le souvenir le porte.
   Rendre un mode indisponible touche la décision partagée avec la plateforme d'expériences.
3. **L'agenda n'est pas décalé** par un retard injecté : la replanification lit le retard de
   l'observation de GAMA, pas celui du choc. C'est le régime actuel
   (`reschedule_activity_departure_time: false`), conservé pour que le run à choc reste comparable
   à son homologue nominal par tout le reste.
4. **La plateforme d'expériences refuse toujours le champ `evenements`** : les chocs sont un
   mécanisme du contrôleur, déclaré dans son propre fichier, comme la loi des accidents.

## Voir aussi

- [`memory-stm-ltm.md`](memory-stm-ltm.md) — la mémoire qui reçoit le choc
- [`accidents-sur-les-axes.md`](accidents-sur-les-axes.md) — les accidents **tirés au sort**, dont
  le retard subi passera par la table de congestion, avec ses deux gardes de cache. Le jour où il
  sera livré, les deux chemins devront écrire dans les mêmes deux champs de retard.
- [`ETAPE_3A_PLAN_LONGITUDINAL.md`](../paper/methode/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md) — le protocole qui consomme cet instrument
