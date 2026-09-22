# Ticket 079 — Des chocs déclarés, vécus par les agents, et qui laissent un souvenir


> ⚠ **AVANT DE LANCER UN RUN GAMA — vérifier l'état des accidents sur les axes.**
> Depuis le 2026-09-15, le paramètre « Accidents sur les axes » (catégorie `Simulation`) est
> **VRAI par défaut**, et depuis le 2026-09-15 les accidents **allongent** les itinéraires
> qui les traversent (ticket 070, travaux C/D/E). Tout run en tire selon la loi BAAC
> 2019-2024, et en subit l'effet. ⚠ **Les runs d'avant et d'après le 2026-09-15 ne sont pas
> comparables.**
> Décocher la case si la mesure doit se faire sur un réseau intact, et **lire
> `accidents_enabled` dans le `scenario_params.yaml`** du run avant d'en interpréter les
> résultats. Détail : [`docs/arch/accidents-sur-les-axes.md`](../arch/accidents-sur-les-axes.md).

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> **LIVRÉ le 2026-09-15 — lots 1 à 4, 34 tests.** `llm/chocs.py`, injection au point unique du
> contrôleur, deux retards séparés partout, colonnes de trace, garde de contenu, cinq cas dans
> `services/llm-agents/config/chocs/`, levier `make run CHOC=<nom>`, documentation
> [`docs/arch/chocs-declares.md`](../arch/chocs-declares.md). Suite complète du dépôt : 1 344 tests
> au vert. **Le lot 5 est transféré au ticket 095 (E3) le 2026-09-21**, et ce ticket est clos.
> Motif : sur les huit runs à choc archivés (2026-09-16 au 2026-09-21), un seul des six cas a
> jamais été joué — `c6_voiture_suspecte`, toujours sur un agent seul. C2 « crevaison », que le
> lot 5 désignait, n'a jamais été exécuté. E3 joue C2, C6 et C3 avec un attendu falsifiable, et
> porte désormais les deux sorties attendues qui restaient d'ici : conformité de `chocs.jsonl`
> à la déclaration pour chacun des trois cas, et un run à exposition **multi-agents** avec
> témoin interne non exposé — la règle `exposition.agents` n'ayant jamais servi qu'avec un seul
> identifiant. Détail dans `scripts/dashboard/tickets_status.yaml`.
>
> **Deux choses que l'implémentation a apprises**, et qui n'étaient pas dans ce texte :
> 1. **Le retard sature à 30 minutes.** Un profil 60/40/25 donnait la MÊME gravité les jours 1 et 2 ;
>    la décrue n'aurait existé que dans le texte. `c1` descend donc à 60/25/12, et la gravité suit :
>    0,70 → 0,62 → 0,37.
> 2. **Tous les cas ne franchissent pas le seuil de choc**, et c'est une information. L'orage
>    plafonne à 0,45 : son souvenir vit 10,4 jours au lieu de 2,8, mais il est rappelé par le mode
>    concerné et non hors contexte. Un orage n'est pas une panne de réseau.
>
> ⚠ **Numérotation.** Créé d'abord sous le n° 078, pris le jour même par
> [le partage de concepts au sein du foyer](ticket_078_partage_de_concepts_au_sein_du_foyer.md)
> dans une autre session. Renuméroté en 079 avant toute référence extérieure.
>
> Ouvert le 2026-09-15. **Rien n'est écrit** : ce ticket est d'abord un cadrage et cinq cas, les
> lots de code ne commencent qu'après validation humaine (plan-first).
>
> **Objet.** Permettre de déclarer un incident — bouchon, crevaison, panne de réseau, train
> supprimé, orage — qui **fait subir un retard** à un agent et lui **laisse un souvenir écrit dans
> ses mots**, sur un ou plusieurs jours, avec une intensité qui peut varier d'un jour à l'autre.
>
> **Pourquoi maintenant.** L'Étape 3a du chapitre 7 mesure l'hystérésis : l'agent évite-t-il encore
> un mode une fois la situation rétablie ? Cela suppose un choc qui laisse une trace. Aujourd'hui
> aucun mécanisme de choc n'existe : le format `Evenement` est accepté, archivé, et
> **l'exécution est refusée** (`services/llm-agents/experiences/experience.py:621-626`).
>
> **Relations.** [041](ticket_041_etape_3a_hysteresis_longitudinale.md) porte le protocole et
> [063](ticket_063_campagne_experimentale_hysteresis_longitudinale.md) la campagne : ce ticket leur
> livre l'instrument qui leur manque. Le [071](ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md)
> a livré la mémoire qui reçoit le choc, et y a laissé **une prise exprès** (§ 2). Le
> [077](ticket_077_la_memoire_apprend_sur_des_observations_fausses.md) répare ce que la mémoire
> apprend : **il est un prérequis dur** (§ 7). Le [070](ticket_070_accidents_aleatoires_sur_les_axes.md)
> pose des accidents **aléatoires** sur les axes ; celui-ci pose des incidents **voulus** — les deux
> se rejoignent sur le retard subi (§ 6).

---

## 1. L'idée, en une phrase

Un choc, c'est **un retard chiffré** plus **une phrase vécue**, posés sur des agents désignés, à des
jours désignés, avec une intensité déclarée jour par jour.

```
  Déclaration (YAML)                Exécution (contrôleur)              Trace
 ┌─────────────────────┐          ┌──────────────────────────┐     ┌──────────────────┐
 │ qui  : mode vélo    │          │ à l'arrivée de l'agent : │     │ qui a été touché │
 │ quand: jour 12      │  ──────► │  + retard   35 min       │ ──► │ combien de retard│
 │ quoi : +35 min      │          │  + phrase   « crevé… »   │     │ quelle phrase    │
 │ mots : « j'ai crevé»│          │  + gravité  incident=oui │     │ quelle gravité   │
 └─────────────────────┘          └──────────────────────────┘     └──────────────────┘
```

C'est tout. Aucun moteur d'itinéraire n'est touché, aucune ligne n'est coupée dans le graphe, aucun
feed GTFS n'est refabriqué.

---

## 2. Pourquoi c'est peu de code : la prise existe déjà

Le ticket 071 a câblé la gravité de bout en bout **avec une composante laissée vide exprès** :

`services/llm-agents/llm/gravite.py:68-82`

| Composante | Poids | Source aujourd'hui |
|---|---|---|
| Retard subi | 0,50 (sature à 30 min) | mesurée à l'arrivée |
| Correspondance ratée | 0,20 | `tc_timeout` |
| **Incident réseau** | **0,20** | **aucune — `COMPOSANTES_INACTIVES`** |
| Mode contraint | 0,10 | contrainte de chaîne |

> *« La chaîne est posée de bout en bout — paramètre, détail, compteur, journal — pour qu'il n'y ait
> qu'une source à brancher le jour venu, et non une formule à rouvrir. »*

**Ce ticket est cette source.**

Et le point d'application est unique. Dans `simulation_controller.py`, à l'arrivée d'un agent
(≈ l. 1917-2040), trois valeurs se rencontrent et rien d'autre n'est à toucher :

```python
_retard_observe_s = max(0, arrive_at - expected_arrive_at)      # ← y ajouter le retard déclaré
_gravite, _detail = gravite_deterministe(
    retard_s=_retard_observe_s,
    correspondance_ratee=(observation.env_ob_code == "tc_timeout"),
)                                                                # ← y passer incident_reseau=True
self.agent.add_short_term_memory(context=_context, msg=ob_text,
                                 timestamp=..., importance=_gravite)  # ← y joindre la phrase
```

Le reste suit tout seul, sans une ligne de plus : la force du souvenir devient
`min(2,8 × (1 + 6·I), 30)` jours, le vivier des chocs le repêche sans condition de contexte dès
0,70, la consolidation se déclenche sur gravité cumulée, le journal de mémoire l'écrit, et le bloc
« Ce qui a changé récemment » du prompt le montre pendant 14 jours.

**Chiffré sur le cas du bouchon :** 60 min de retard saturent la composante retard à 0,50 ;
`incident_reseau` ajoute 0,20 ; total **0,70**, soit exactement le seuil du vivier des chocs. Durée
de vie : **14,6 jours** au lieu de 2,8. C'est cela, et rien d'autre, qui rend l'hystérésis
mesurable.

---

## 3. Deux régimes, et il faut les distinguer avant de coder

C'est la décision structurante du ticket.

| | **Choc subi** (imprévu) | **Choc anticipé** (connu à l'avance) |
|---|---|---|
| Ce que l'agent sait en décidant | rien : il voit l'offre nominale | l'offre est dégradée sous ses yeux |
| Ce qu'il subit | retard + souvenir, **après** la décision | il choisit déjà en conséquence |
| Ce qu'on mesure | **l'hystérésis pure** : le jour J ne dit rien du choix, tout se lit à J+1 | l'adaptation sous contrainte |
| Ce qu'il faut coder | ce ticket, § 2 | couper la ligne dans le calculateur, plus la garde de cache |
| Coût | **faible** | moyen |
| Exemples | bouchon, crevaison, orage, panne soudaine | grève annoncée, travaux, fermeture programmée |

**Ce ticket ne livre que le régime subi.** C'est le moins cher *et* le plus propre pour H3 : l'agent
a choisi sous information nominale, il a subi, il se souvient. Le jour du choc ne mesure donc aucun
choix — et c'est une qualité, pas un défaut : tout l'effet observé les jours suivants est imputable
au souvenir, jamais à la contrainte.

⚠ **Limite à publier.** Le manuscrit (§ 5.3) exige que l'événement soit *« le même événement déclaré
deux fois, une fois en langue et une fois en graphe »*. Le régime subi ne le déclare **qu'une fois**,
en langue. C'est légitime pour un incident imprévu — personne ne connaît la panne avant de la subir
— mais cela doit être **écrit dans l'article**, pas laissé implicite. Le régime anticipé, s'il est
ouvert un jour, relève d'un autre ticket.

---

## 4. Les cinq cas, un par famille de mode

Tous les modes du dépôt sont couverts : voiture, vélo, transports en commun, marche, train,
deux-roues motorisés. Les valeurs ci-dessous sont des **propositions à valider**, pas des mesures.

### C1 — Bouchon monstre sur la rocade · **voiture**, deux-roues motorisés
Collectif, **3 jours d'affilée, intensité décroissante**. C'est le cas qui exerce le profil par jour.

| Jour | Retard | Ce que l'agent retient |
|---|---|---|
| J | 60 min | « Bloqué une heure sur la rocade, pare-chocs contre pare-chocs. Des gens klaxonnaient, un type est sorti de sa voiture. Je suis arrivé en nage et de mauvaise humeur. » |
| J+1 | 25 min | « Encore la rocade. Moins long qu'hier mais j'ai su tout de suite que c'était reparti. » |
| J+2 | 12 min | « Toujours ralenti. Je commence à me demander si ça vaut le coup. » |

*Exposition :* tout agent dont le trajet du jour est en voiture ou en deux-roues motorisé. Variante
resserrée : uniquement ceux dont l'origine ou la destination est hors de la 1ʳᵉ couronne.

### C2 — Crevaison · **vélo**
Individuel, **1 jour**, plus une conséquence le lendemain. Le cas demandé, et le plus intéressant :
**rien dans le graphe ne change**, l'effet ne peut venir que de la mémoire.

| Jour | Retard | Ce que l'agent retient |
|---|---|---|
| J | 35 min | « Crevaison en plein trajet. J'ai mis vingt minutes à réparer sur le trottoir, les mains pleines de cambouis, et j'ai fini à pied en poussant le vélo. Je suis arrivé en retard et sale. » |
| J+1 | 0 min | vélo **indisponible** (`has_bike = false` pour la journée) — la contrainte de mode ajoute 0,10 à la gravité |

*Exposition :* tirage à graine fixe parmi les agents possédant un vélo et l'utilisant ce jour-là ;
les non tirés sont le **témoin interne**.

### C3 — Panne du réseau · **transports en commun**
Collectif, **2 jours**. Le seul cas qui atteint naturellement la correspondance ratée.

| Jour | Retard | Correspondance | Ce que l'agent retient |
|---|---|---|---|
| J | 45 min | ratée | « Le métro s'est arrêté entre deux stations, lumière éteinte, personne ne disait rien. On nous a fait sortir et j'ai raté ma correspondance. Quai noir de monde. » |
| J+1 | 20 min | — | « Trafic perturbé toute la matinée, rames bondées. » |

*Gravité :* 0,50 (retard saturé) + 0,20 (correspondance) + 0,20 (incident) = **0,90**, soit 17,9
jours de durée de vie. C'est le choc le plus marquant des cinq, et c'est celui du chapitre 7.

### C4 — Train supprimé · **train**
Collectif ciblé, **1 jour**. Peu d'agents concernés, gravité forte.

| Jour | Retard | Ce que l'agent retient |
|---|---|---|
| J | 50 min | « Mon TER a été supprimé sans explication. J'ai attendu le suivant cinquante minutes sur un quai sans abri. » |

*Exposition :* agents dont le trajet du jour comporte une jambe ferroviaire.

### C5 — Orage de grêle · **marche**, vélo, deux-roues motorisés
Collectif, **1 jour**. Frappe les modes exposés, ceux que les quatre autres cas laissent de côté.

| Jour | Retard | Ce que l'agent retient |
|---|---|---|
| J | 15 min | « Orage violent en pleine rue, grêle. Je me suis abrité sous un porche vingt minutes et je suis arrivé trempé jusqu'aux os, chaussures pleines d'eau. » |

*Note :* c'est ici, et seulement ici, qu'un choc météo devient mémorable. Une canicule seule ne
produit **aucun** retard, donc une gravité nulle et une durée de vie de 2,8 jours ; elle change la
décision du jour et ne laisse rien derrière elle (cf. plan Étape 3a, § 4 bis). Déclarer l'orage
comme incident lui donne l'ancrage mesuré qui lui manque.

### Couverture

| Mode | C1 | C2 | C3 | C4 | C5 |
|---|:-:|:-:|:-:|:-:|:-:|
| Voiture | ● | | | | |
| Vélo | | ● | | | ● |
| Transports en commun | | | ● | | |
| Marche | | | | | ● |
| Train | | | | ● | |
| Deux-roues motorisés | ● | | | | ● |

---

## 5. Comment ça se déclare

Un fichier par choc, à côté de l'expérience. Le format **étend** `Evenement`
(`experience.py:183-202`) plutôt que d'en créer un second, et ajoute ce qui lui manque : le profil
par jour, le retard, le texte vécu, et la règle d'exposition.

```yaml
# specs/ticket_079/exemples/c1_bouchon_rocade.yaml
choc: c1_bouchon_rocade
type: incident
libelle: "Bouchon majeur sur la rocade"
source: "fictif — calibré sur les élasticités de Zhu et al. (2010)"

exposition:
  regle: mode            # mode | ligne | zone | tirage | agents
  modes: [car, motorbike]
  # tirage: {part: 0.3, graine: 78}     # pour un choc individuel (C2)
  # agents: ["609", "41275"]            # pour désigner nommément

jours:
  - jour: 12             # rang du jour simulé, 1 = premier jour du run
    retard_min: 60
    incident_reseau: true
    vecu: >-
      Bloqué une heure sur la rocade, pare-chocs contre pare-chocs. Des gens
      klaxonnaient, un type est sorti de sa voiture. Je suis arrivé en nage et
      de mauvaise humeur.
  - jour: 13
    retard_min: 40
    incident_reseau: true
    vecu: "Encore la rocade. Moins long qu'hier mais j'ai su tout de suite que c'était reparti."
  - jour: 14
    retard_min: 25
    incident_reseau: true
    vecu: "Toujours ralenti. Je commence à me demander si ça vaut le coup."
```

**Règles de forme, à tenir :**

- `vecu` est **du vécu, jamais une consigne**. « Je suis arrivé en retard et sale » est admis ;
  « tu devrais éviter le vélo demain » ne l'est pas. Le format `Evenement` porte déjà cette règle sur
  son champ `description` (*« texte porté aux agents, jamais consigne »*) ; ici elle devient
  **vérifiable** (§ 8, lot 4).
- Une journée sans entrée dans `jours` est une journée **nominale**. Il n'y a pas de choc « en
  cours » implicite.
- `retard_min: 0` est légitime : un choc peut être pénible sans retarder (C2 au jour J+1).
- Le choc est **déclaré en jours de run**, pas en dates : il suit le calendrier du run et survit à un
  décalage de la date de départ.

---

## 6. Où cela se branche, et les trois pièges

### Le point d'injection
Un seul, déjà identifié au § 2 : le traitement de l'observation d'arrivée dans
`simulation_controller.py`. Un module neuf `llm/chocs.py` lit la déclaration, répond à trois
questions — *cet agent est-il exposé aujourd'hui ? quel retard ? quelle phrase ?* — et le contrôleur
applique. Aucun appel au modèle, aucune dépendance nouvelle.

### Piège 1 — Le retard injecté ne doit jamais se confondre avec le retard mesuré
Deux champs distincts, partout : `retard_mesure_s` (ce que GAMA a produit) et `retard_injecte_s` (ce
que le choc a déclaré). La gravité utilise la somme ; les journaux portent les deux. Sans cette
séparation, aucune trace ne permettra plus jamais de dire ce que la simulation a fait et ce qu'on lui
a fait dire — et une mesure d'hystérésis sans cette distinction n'est pas publiable.

### Piège 2 — Le cache de décisions
`llm/cache.py:208-248` bâtit sa clé sur les codes d'options, la météo et `extra_key` : **aucune durée
n'y entre**, et le choc n'y entrerait pas non plus. Or le souvenir, lui, change le prompt. Deux
parades possibles : porter la signature du choc dans `extra_key` (le champ existe, l'anticipation du
ticket 014 s'en sert déjà), ou constater que le cache sert 0 % en régime nominal et le laisser coupé
pendant les campagnes. **À trancher** (question 3).

### Piège 3 — La cascade sur l'agenda
`reschedule_activity_departure_time` vaut `false` aujourd'hui : un retard ne décale pas les activités
suivantes. Un retard injecté d'une heure produirait donc un agent en retard **qui ne rattrape rien**,
ce qui est cohérent avec le régime actuel mais doit être dit. **À trancher** (question 2).

### Ce que ce ticket ne fait pas
- Il ne coupe aucune ligne, ne dégrade aucune fréquence, ne touche ni OTP ni GTFS ni OSMnx.
- Il ne rend pas l'oracle tabulaire sensible au choc : par construction l'oracle ne voit ni retard
  vécu ni souvenir, et c'est précisément ce que le bras O doit démontrer.
- Il ne recouvre pas le ticket 070 : là-bas les accidents sont **tirés au sort** et leur retard
  passera par la table de congestion, avec ses deux gardes de cache ; ici les incidents sont
  **voulus** et leur retard est déclaré. Le jour où le 070 livrera le retard subi, les deux chemins
  devront écrire dans les mêmes deux champs (piège 1) — c'est la seule dépendance à tenir.

---

## 7. Prérequis dur : le ticket 077

Un choc n'est mesurable que si ce que la mémoire apprend est vrai. Le run de 32 jours a montré
398 marches fantômes sur 412 et 253 trajets voiture journalisés en transport collectif. **Injecter
un choc dans cette chaîne produirait un souvenir juste noyé dans des souvenirs faux.**

Les lots A, B et C du 077 sont donc à livrer avant tout run de mesure de ce ticket. Rien n'empêche
en revanche de **développer** les deux en parallèle : les points de code ne se recouvrent pas.

---

## 8. Lots

| Lot | Contenu | Coût | Dépend de |
|---|---|---|---|
| **0** | **Décisions** : les trois questions du § 9, plus validation des cinq cas et de leurs valeurs | — | humain |
| **1** | Format de déclaration et lecture : extension d'`Evenement`, `llm/chocs.py`, refus explicites (jour hors run, mode inconnu, `vecu` vide, texte impératif) | S | lot 0 |
| **2** | Injection : retard, phrase, `incident_reseau`, les deux champs séparés du piège 1 ; levée du refus `experience.py:621-626` pour le seul régime subi | S | lot 1 |
| **3** | Trace : § 9 ci-dessous | S | lot 2 |
| **4** | Garde de contenu : un `vecu` impératif est **refusé au chargement**, pas signalé au journal | S | lot 1 |
| **5** | Les cinq cas en fichiers d'exemple, et une répétition générale à 5 agents sur C2 (crevaison) — le cas où rien ne change dans le graphe | ~1 j de quota | 077 A/B/C |

---

## 9. Ce qu'il faut enregistrer, et ce que le 077 n'en couvre pas

**Vérifié :** le lot E du 077 instrumente les souvenirs servis, l'index proposé et tiré, les options
présentées, les `known_beliefs`, le statut cache, et demande un run témoin sans mémoire. **Il ne dit
rien du choc lui-même** — ce qui est normal, il a été écrit avant ce ticket.

Manquent, et ce ticket les porte plutôt que d'aller modifier un 077 déjà en cours dans une autre
session :

| À enregistrer | Où | Pourquoi |
|---|---|---|
| `choc_id`, `jour_du_choc` (rang relatif : −2, −1, **0**, +1, +2…) | `moves.csv`, une colonne | c'est l'abscisse de toutes les courbes d'hystérésis |
| `expose` (booléen) et **la raison** de l'exposition | `moves.csv` | les non exposés sont le témoin interne du même run |
| `retard_mesure_s` et `retard_injecte_s`, séparés | `moves.csv`, `gama_arrivals.csv` | piège 1 |
| `vecu_injecte` (le texte exact) et `doc_id` du souvenir qu'il a produit | `agent_memory_events.jsonl` | relier le choc au souvenir, puis le souvenir aux décisions via le lot E du 077 |
| Gravité obtenue et **détail par composante** | idem | vérifier que le choc a bien franchi 0,70, et par quoi |
| Déclaration complète + empreinte du fichier | `<workdir>/choc.yaml` | reproductibilité |
| `periode` : `avant` / `pendant` / `apres` | `moves.csv` | le champ existe déjà dans `experiences/decision.py:271` et **rien ne l'écrit** ; ici il aurait enfin une source |

**Si l'autre session préfère tout centraliser**, une seule ligne suffit à ajouter au lot E du 077 :
*« 7. Le choc : identifiant, jour relatif, exposition et sa raison, retard injecté distinct du
retard mesuré, texte vécu et identifiant du souvenir produit. »* Les deux voies sont acceptables ;
il faut juste en choisir une.

---

## 10. Questions ouvertes

1. **Le régime anticipé, jamais ou plus tard ?** Ce ticket ne livre que le choc subi. Une grève
   annoncée, où l'agent choisit en connaissant la dégradation, demande de couper l'offre dans le
   calculateur. *Hypothèse retenue :* plus tard, dans un ticket séparé, et la limite est écrite dans
   l'article.
2. **Le retard injecté décale-t-il les activités suivantes ?** *Hypothèse retenue :* non, on garde le
   régime actuel (`reschedule_activity_departure_time: false`) et on le déclare. *Alternative :*
   l'activer pour les seuls jours de choc, ce qui rendrait la journée réellement désorganisée mais
   ferait diverger le run de son homologue nominal par autre chose que la mémoire.
3. **Le cache de décisions pendant une campagne à choc :** signature du choc dans `extra_key`, ou
   cache coupé ? *Hypothèse retenue :* coupé, puisqu'il sert 0 % en régime nominal et que c'est
   l'option la plus sûre.
4. **Les valeurs des cinq cas** (retards, textes, durées) sont des propositions. Faut-il les ancrer
   sur une source — élasticités publiées après grèves et fermetures — ou les assumer comme un
   scénario déclaré ? *Hypothèse retenue :* assumées comme scénario, avec la source citée en regard
   quand elle existe.
5. **Un choc doit-il pouvoir toucher un agent qui n'a pas utilisé le mode ?** Par exemple : le
   bouchon retarde-t-il aussi le bus pris dans le même trafic ? *Hypothèse retenue :* non au premier
   lot, une règle d'exposition par mode et rien de plus.

---

## Le choc à jouer à la campagne suivante — arbitrage du 2026-09-22

La campagne du § 7.2 de l'article a tourné sur `c6_voiture_suspecte`, « Engine trouble » : le
moteur cale sur la voie rapide, dépannage, trente minutes de retard, puis vingt le lendemain.
L'auteur a relevé le défaut à la relecture, et il est réel : **une panne de cette nature
immobiliserait le véhicule**. Or la simulation continue de proposer la voiture le lendemain, et
c'est précisément ce que le chapitre met en avant — « la voiture est offerte aussi souvent
qu'avant, et cesse d'être prise ». L'argument porte sur un monde que la panne n'aurait pas laissé
intact.

**Le cas à jouer est le C1, le bouchon monstre sur la rocade**, et il est déjà écrit au § 4 :

- **le véhicule reste disponible sans réserve.** Un embouteillage ne met personne au garage ;
  l'arbitrage mesuré est alors un vrai arbitrage, et la phrase du chapitre tient sans réserve ;
- **son profil décroît sur trois jours**, 60 puis 25 puis 12 minutes. C'est le cas qui exerce la
  durée dérivée de la gravité, là où C6 tenait sur deux jours ;
- **il peut se reproduire**, ce qui ouvre la voie d'extinction par contradiction. La campagne C6
  n'a fourni qu'un cas d'extinction par usure, et le chapitre le dit ; la prédiction de
  stratification du § 7.1 a besoin de l'autre.

Le cas **C2, la crevaison**, est le contre-exemple utile et il reste au dossier tel quel : au
jour J+1 le vélo est **indisponible**, `has_bike = false`, et la contrainte de mode ajoute 0,10 à
la gravité. Le dépôt sait donc déjà distinguer « le mode reste offert » de « le mode disparaît » ;
c'est le choix du choc qui ne l'avait pas fait.

⚠ **Les chiffres publiés au § 7.2 restent ceux de C6** et ne se remplacent pas par ceux de C1 :
ce sont deux campagnes. Tant que C1 n'est pas jouée, le chapitre garde C6 et sa réserve écrite.
