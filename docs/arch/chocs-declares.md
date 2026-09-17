# Chocs déclarés, subis par les agents

> Ticket [079](../tickets/ticket_079_chocs_declares_vecus_par_les_agents.md). Contrat de test :
> [`specs/ticket_079/tests.md`](../../specs/ticket_079/tests.md). Livré le 2026-09-15, 34 tests.

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

Les cas livrés sont dans [`services/llm-agents/config/chocs/`](../../services/llm-agents/config/chocs/) :
`c1_bouchon_rocade`, `c2_crevaison`, `c3_panne_reseau`, `c4_train_supprime`, `c5_orage_grele`. Ils
couvrent les six modes du dépôt.

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

| Choc | Retard | Composantes | Gravité | Durée de vie |
|---|---|---|---|---|
| Trajet banal | 0 | — | 0,00 | **2,8 j** |
| Orage (c5) | 15 min | retard 0,25 + incident 0,20 | 0,45 | 10,4 j |
| Bouchon (c1, jour 3) | 12 min | retard 0,17 + incident 0,20 | 0,37 | 9,0 j |
| Bouchon (c1, jour 2) | 25 min | retard 0,42 + incident 0,20 | 0,62 | 13,2 j |
| Crevaison (c2) · Bouchon (c1, jour 1) · Train (c4) | ≥ 30 min | retard 0,50 + incident 0,20 | **0,70** | **14,6 j** |
| Panne réseau (c3) | 45 min + corresp. ratée | 0,50 + 0,20 + 0,20 | **0,90** | **17,9 j** |

⚠ **La composante de retard sature à 30 minutes** (`memoire__retard_ref_s` = 1800 s). Au-delà,
déclarer 45, 60 ou 90 minutes donne rigoureusement la même gravité. Un profil décroissant qui
resterait tout entier au-dessus de 30 minutes serait donc **invisible du mécanisme** et n'existerait
que dans le texte : c'est pourquoi `c1` descend à 25 puis 12 minutes. C'est le premier piège de
toute nouvelle déclaration.

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
