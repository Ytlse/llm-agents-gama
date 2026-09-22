# Ticket 100 — banc de tests fonctionnels

Écrit le 2026-09-22, à la demande de l'auteur : *« un maximum de tests avec un minimum
d'appels »*, pour trouver les défauts **avant** qu'une campagne longue ne consomme le quota.

Plan : [`plan.md`](plan.md) · Contrat unitaire : [`tests.md`](tests.md) · Questions :
[`questions.md`](questions.md).

---

## 1. Le principe : un stub par frontière, un appel par inconnue

Le dépôt porte déjà **1 900 tests unitaires** sur ce ticket. Ils vérifient des règles, pas des
chaînes : chacun appelle une fonction et regarde ce qu'elle rend. Ce que personne n'a vérifié,
c'est que **les maillons tiennent ensemble**, et ce qu'un modèle réel fait des deux prompts
nouveaux.

D'où deux familles, et la séparation est la seule idée de ce document :

| Famille | Ce qu'elle vérifie | Appels |
|---|---|---|
| **A** | que la chaîne tient : injection → mémoire → décision → trace → mesure → figure | **0** |
| **B** | ce qu'un modèle réel fait des deux prompts que ce ticket ajoute | **27** |

**Tout ce qui n'est pas une question posée au modèle est stubé.** Un itinéraire, une réflexion
du soir, une population, un point de reprise : ces objets ont un format, pas une intelligence.
Les fabriquer à la main coûte zéro token et les rend *reproductibles*, ce qu'un run ne sera
jamais.

**Aucun test n'attend une journée simulée.** Les huit jours qu'il faudrait pour observer une
consolidation se remplacent par une entrée de mémoire écrite à la main avec le bon horodatage.
C'est le même objet, au même endroit, lu par le même code.

---

## 2. Le budget, et la contrainte de passerelle

**Aujourd'hui : Groq seul** (décision de l'auteur, 2026-09-22). Trois instances déclarées —
`groq_openai_120_key1` (gpt-oss-120b), `groq_openai_20_key1` (gpt-oss-20b),
`groq_qwen_qwen3_8_27b_key1`. Les tests longue durée passeront plus tard sur d'autres modèles ;
le banc en fait donc un **paramètre déclaré**, pas une constante, et il **écrit dans chaque
résultat quelle instance a servi**. Sans cela, deux campagnes sur deux passerelles seraient
incomparables sans qu'on puisse le dire.

⚠ **Pas de repli.** Si le quota Groq est épuisé, le banc **attend** ou **s'arrête** ; il ne
bascule sur aucune autre instance. Une mesure obtenue sur une passerelle qu'on n'a pas déclarée
n'est pas la mesure qu'on croit lire.

⚠ **La limite qui mord n'est pas celle qu'on croit.** Groq a été écarté des campagnes le
2026-09-08 pour une limite mesurée de **1 000 jetons de SORTIE par minute**, invisible hors du
corps des 429, et la passerelle n'a pas été corrigée. Les 30 requêtes/minute et les
1 000 requêtes/jour ne seront jamais atteintes ici ; **l'OTPM le sera**. D'où la conception :

- `max_tokens: 256` sur le jugement, `1024` sur la réflexion — les schémas sont courts ;
- les appels partent **en série**, jamais en rafale ;
- le banc **compte ses jetons de sortie** et s'arrête au budget déclaré plutôt que de découvrir
  la limite dans un 429 muet.

**Budget total : 27 appels, ≈ 6 000 jetons de sortie.** Soit six minutes d'attente au pire, et
moins de 3 % du quota journalier d'une seule clé.

---

## 3. Famille A — le run synthétique, zéro appel

**Une seule expérience, et c'est la plus rentable du banc.** On fabrique un run complet de
vingt jours simulés — population, décisions, mémoire, événement, points de reprise — sans
simulateur et sans modèle, puis on fait tourner dessus **toute la chaîne d'analyse réelle**.

Ce que cela attrape, et qu'aucun test unitaire n'attrape : une colonne mal nommée, un rôle qui
ne se propage pas, une trace que le dépouilleur ne sait pas lire, une figure qui sort vide, un
jour relatif décalé d'un cran.

| # | Ce qui est joué | Attendu | Ce qui le falsifierait |
|---|---|---|---|
| **A1** | Bascule de journée à 3 h, un article dû pour deux lecteurs sur six foyers | L'entrée est en mémoire **courte ET longue** avant la première décision du jour | L'article n'atteint la mémoire longue que le soir → le régime ne fait pas ce qu'il annonce |
| **A2** | Gravité de l'entrée déposée, jugement stubé à `notable` (0,30) | `importance = 0,30`, `force = 7,84 j` — l'estimation **seule** (D7) | Une valeur de 0,70 : le plancher n'a pas été retiré |
| **A3** | Le co-résident non tiré, même foyer, même journée | **Rien** reçu : ni entrée, ni gravité, ni ligne de trace | Une entrée chez lui → le témoin interne n'existe plus et l'étage de diffusion perd son objet |
| **A4** | Trois nuits de foyer, A raconte, B écoute, B reconsolide | B ne réentend **jamais** le même bilan ; une croyance `entendu` de B ne repart pas | Un bilan servi deux fois, ou une croyance d'ouï-dire qui repart → la boucle est ouverte |
| **A5** | Reprise à chaud au jour 12, puis rejeu jusqu'au 14 | Aucun bilan déjà entendu n'est resservi ; **aucune** entrée écrite pendant le gel | Une ré-écoute → le repère ne survit pas au point de reprise |
| **A6** | Un jour d'événement tombant dans la fenêtre de rejeu | Refus au chargement **ou** `[ALARME]`, et **rien** d'écrit | Une injection silencieuse → le protocole a sauté sans trace |
| **A7** | 20 jours de décisions, cache actif | Cache coupé les seuls jours d'événement ; compteurs journaliers non nuls sur la fenêtre d'après | Un compteur muet → la réserve de Q5 n'est pas mesurable |
| **A8** | `evenements.jsonl` produit | **Une** ligne par exposition, sur les quatre chemins de sortie du jugement | Deux lignes → tout compte par exposition est faux |
| **A9** | `mesures`, `figure_evenement.py`, `tableau_quatre_voies.py` sur ce run | Les trois produisent leur sortie ; la figure porte les trois rôles | Une sortie vide ou une exception → la chaîne d'analyse ne lit pas ce que le run écrit |
| **A10** | `campagne.py` sur cinq runs synthétiques, un par article | Rapport avec empreinte de grille, plancher déclaré, intervalle groupé par événement | Un binomial réapparaît, ou un plancher par défaut |

**Coût : zéro appel, quelques secondes.** À relancer à chaque modification du ticket.

---

## 4. Famille B — les deux prompts, et rien d'autre

Le ticket n'ajoute que **deux** demandes au modèle. Tout le reste de sa mécanique est
déterministe et couvert par A. Le budget d'appels va donc entièrement à ces deux-là.

### B1 — L'échelle du jugement est-elle utilisée ? · **15 appels**

*3 personas × 5 textes d'événement.* Personas pris dans la population scellée, textes pris dans
`config/evenements/`.

| Attendu | Pourquoi c'est la question qui compte |
|---|---|
| Les cinq échelons apparaissent sur l'ensemble des quinze réponses | Depuis D7, la gravité **est** le jugement. Un modèle qui répond `noticeable` à tout rend toutes les durées de vie identiques, et E3 du ticket 095 ne mesurerait plus rien |
| Aucune réponse hors énumération | Le refus est franc : chaque hors-grille est une exposition perdue |
| Les `modes` rendus recoupent ceux que la grille prédit | C'est le **troisième niveau de mesure** — ce que l'agent a compris du texte — confrontable à la grille **sans attendre qu'il se déplace** |

**Ce qui falsifierait le dispositif :** une réponse constante quel que soit le texte. Le
jugement ne mesurerait alors pas le texte mais le prompt, et le canal `lu` serait inerte.

### B2 — Le modèle dit-il `heard` ? · **4 appels**

*2 agents × 2 conditions (avec bloc foyer / sans).* La journée de l'agent est stubée : trois
entrées de mémoire courte écrites à la main. Le bloc foyer est produit par `llm/foyer.py` sur
une mémoire longue stubée.

| Attendu | Pourquoi |
|---|---|
| **Sans** bloc : tous les concepts portent `source: lived` | Le champ est demandé dans les deux bras pour garder une version de schéma unique |
| **Avec** bloc : au moins un concept né du bloc porte `source: heard` | **C'est le test qui peut invalider le lot 4 en entier.** Si le modèle ne dit jamais `heard`, la règle du saut unique ne s'engage jamais, `origine` reste `vecu` partout, et tout ce qui est entendu recircule |
| Le schéma v4 est respecté (11 champs requis, `additionalProperties: false`) | Un schéma refusé par le fournisseur ferait échouer **toutes** les consolidations |

⚠ **Ce test est le plus important du banc.** Son échec est silencieux en production : rien ne
plante, les croyances circulent simplement sans provenance, et D2 devient décoratif.

### B3 — Le plancher de bruit du JUGEMENT · **8 appels**

*2 couples (persona, texte) × 4 répétitions, température 0,2, mêmes entrées.*

Le ticket 095 a mesuré un plancher de bruit sur les **décisions** : 3,2 %. Depuis D7, il en faut
un second, sur les **jugements** — parce que la gravité, donc la durée de vie du souvenir, en
dépend désormais entièrement.

| Attendu | Ce qu'on en fait |
|---|---|
| Les quatre répétitions rendent le même échelon | Si oui, une différence de gravité entre deux bras est interprétable |
| Sinon : l'amplitude en échelons, et l'écart de durée de vie qu'elle implique | **Ce chiffre se déclare avec tout résultat de gravité**, comme les 3,2 % se déclarent avec tout écart de part modale |

**Ce qui falsifierait E3 du ticket 095 :** une variation d'un échelon d'une répétition à
l'autre. `notable` → `genant` fait passer la durée de vie de 7,8 à 11,2 jours — soit plus que
l'écart que E3 cherche à mesurer entre deux chocs déclarés.

### B4 — Le hors-grille · **0 appel**

On ne provoque pas une réponse aberrante à la demande. Le chemin de refus est couvert par stub
(déjà fait, `test_100_lot3_jugement.py`). Ce que B1 à B3 mesurent **gratuitement**, c'est le
**taux réel** de réponses hors schéma sur 27 appels — observation, pas test.

---

## 5. Les stubs à implémenter

Tous dans `scripts/experiment/banc_fonctionnel/stubs.py`. Aucun ne simule une intelligence :
chacun fabrique un objet dont le **format** est celui du dépôt.

| Stub | Ce qu'il fabrique | D'où vient sa forme |
|---|---|---|
| `population_de_banc()` | 12 agents, 6 foyers de 2, avec `household_id`, traits contrastés (permis, vélo, abonnement) | `population_20_foyers_059/MANIFEST.yaml` |
| `memoire_longue_stub()` | Un `user_metadata` complet : réflexions datées, concepts avec compteurs, axes renseignés | `llm/memory.py:MemoryEntry`, lu par `foyer.py` et `longterm.py` |
| `journee_stub()` | Trois entrées de mémoire courte — décision, arrivée, contrainte de chaîne | ce que le contrôleur écrit réellement |
| `itineraires_stub()` | Deux à quatre propositions par déplacement, modes et durées | format d'option d'OTP, sans appeler OTP |
| `moves_stub()` | Un `moves.csv` aux 50 colonnes réelles, 20 jours, 3 rôles | `move_logger.CSV_HEADERS` — **importé**, jamais recopié |
| `point_de_reprise_stub()` | Un répertoire `checkpoints_memoire/jour_NNN/` valide | `utils/reprise.py:_A_COPIER` |
| `ClientJugementStub` | Rend un échelon déclaré, ou une réponse volontairement aberrante | schéma `evenement_jugement` |
| `ClientReflexionStub` | Rend une réflexion et des concepts, `source` déclarée | schéma `stm_reflection` v4 |

**Règle unique et non négociable pour les stubs de format** : ils **importent** la définition
du dépôt (`CSV_HEADERS`, `MemoryEntry`, les schémas JSON) au lieu de la recopier. Un stub qui
recopie une liste de colonnes teste sa propre copie, et il passe au vert le jour où le vrai
format change. C'est la leçon du lot A du ticket 077.

---

## 6. Les observations, et à quelle figure elles servent

Ce que le banc doit **écrire**, au-delà du vert ou du rouge. C'est la partie qui sert le papier.

| Observation | Fichier | Ce qu'elle rend possible |
|---|---|---|
| Échelon jugé, par persona et par article | `jugements.csv` | **Figure « troisième niveau de mesure »** : ce que l'agent a compris de chaque texte, confronté à la grille — sans attendre un déplacement, donc sans campagne |
| Modes cités par le jugement, contre modes prédits par la grille | `jugements.csv` | Accord de signe **avant** toute mesure comportementale : un second point d'appui pour le § 7.3 |
| Amplitude des répétitions, en échelons et en jours de durée de vie | `plancher_jugement.md` | **Chiffre à déclarer avec tout résultat de gravité**, comme les 3,2 % du 095 |
| Taux de `source: heard` avec et sans bloc foyer | `provenance.csv` | Dit si l'étage de diffusion est observable **avant** de payer une campagne de 40 jours |
| Taux de réponses hors schéma, par instance | `passerelle.csv` | Choix du modèle pour la campagne, et comparabilité avec les runs longs d'une autre passerelle |
| Jetons de sortie consommés, par appel | `passerelle.csv` | Calibre le coût réel d'une campagne — l'OTPM est la limite qui mord |

⚠ **Aucune de ces observations ne remplace une campagne.** Elles disent si une campagne a une
chance de mesurer quelque chose. Un banc vert ne prouve pas un effet ; un banc rouge évite de
payer quarante jours pour l'apprendre.

---

## 7. Ce que le banc ne teste pas, et il faut le savoir

- **Le chemin GAMA.** Rien ici ne parle à GAMA. Le run court de non-régression sur `c6` reste
  le seul test de cette frontière, et il n'est pas remplaçable par un stub.
- **Un effet de comportement.** Aucun agent ne se déplace. Le banc vérifie que la mécanique
  transporte ce qu'elle doit ; il ne dit rien de ce qu'un agent ferait.
- **La durée.** L'oubli sur trente jours ne se stube pas honnêtement : on peut écrire une entrée
  vieille de trente jours, mais pas les trente jours de rappels qui l'ont usée.
- **Le coût réel d'une campagne.** Le banc mesure des jetons par appel, pas le nombre d'appels
  qu'une campagne fera — cela dépend du nombre de décisions, qui dépend des agents.

---

## 8. Ordre d'exécution

1. **Famille A**, zéro appel. Si elle échoue, rien d'autre n'a de sens à lancer.
2. **B2** (4 appels) — c'est le test dont l'échec est silencieux en production. Le passer en
   premier permet d'arrêter là si le modèle ignore le champ de provenance.
3. **B3** (8 appels) — le plancher de bruit du jugement. Il conditionne l'interprétation de B1.
4. **B1** (15 appels) — l'échelle, qui est aussi la première observation publiable.

À chaque étape, le banc écrit ses observations avant de passer à la suivante : une interruption
de quota ne doit pas faire perdre ce qui a été payé.
