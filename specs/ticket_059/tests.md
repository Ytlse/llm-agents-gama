# Ticket 059 — contrat de tests

Écrit AVANT le code, le 2026-09-21. **Les prédictions du § 3 sont posées avant tout run et ne se
réécrivent pas après mesure.**

Plan d'architecture : [`plan.md`](plan.md). Questions ouvertes : [`questions.md`](questions.md).

---

## Le besoin

Le chapitre 7 § 7.1 annonce vingt prédictions signées, un taux d'accord de signe et deux contrôles.
Rien de tout cela n'est vérifiable au dépôt : le corpus textuel n'existe pas, la grille a trois
cellules ambiguës, et le script d'injection n'est pas écrit. Par ailleurs, un article ne fait subir
aucun retard : passé par le canal des chocs, il porterait une gravité nulle et sortirait du prompt
le surlendemain — l'étage longitudinal n'aurait rien à mesurer, et son silence passerait pour une
absence d'effet.

Vérifié dans le code avant d'écrire ce contrat :

- `llm/gravite.py` calcule `force = min(S0 × (1 + k·I), 30)` avec `S0 = 2,8` ; une entrée
  d'importance 0,00 vit 2,8 jours, une entrée d'importance 0,70 en vit 14,6.
- `llm/chocs.py` applique le choc à l'**arrivée** (`simulation_controller.py` ≈ l. 2086, sur
  `env_ob_code == "arrival"`). Aucun chemin n'existe pour une entrée posée **avant** la décision.
- `experiences/experience.py` accepte `Evenement.type ∈ {incident, information}` et **refuse
  l'exécution des deux** (l. 677-680).
- `enquetes.py` sert déjà le bloc mémoire complet et cinq prompts par jalon (095, lot B) ; les
  jalons se déclarent par `EXPERIMENT_SURVEY_DAYS`.
- La cohorte v6 porte `household.id` sur **tous** les agents ; 217 foyers multi-membres ont tous
  leurs membres mobiles, dont 122 de taille 2.

---

## Les principes

**Une prédiction se gèle avec son empreinte.** La grille et le corpus portent un SHA-256, et tout
rapport de dépouillement les recopie en tête. Une grille modifiée après une campagne se voit ; sans
empreinte, le « pré-enregistré » n'est qu'une affirmation.

**Un texte de presse est cité, jamais réécrit.** C'est la garde propre à ce canal, et elle n'a pas
d'équivalent chez les chocs, dont le `vecu` est écrit par nous. Le texte injecté est comparé à son
empreinte à chaque chargement.

**La traduction est la seule réécriture admise, et elle se déclare.** Les cinq articles sont
français, le dispositif est anglais (ticket 074). Décision de l'auteur du 2026-09-21 : on traduit,
les deux versions sont gelées avec leurs empreintes, et l'entrée servie à l'agent porte la mention
« Translated from French ». Une traduction servie comme un original serait une sixième condition
non déclarée.

**Une paraphrase sans indice modal se vérifie, elle ne se déclare pas.** La liste des mots
interdits vit dans un fichier ; un mot qui passe rend la condition C3 sans objet, donc le refus est
franc.

**La gravité d'un article est une constante, identique aux cinq.** Une gravité par article
ramènerait la durée de l'effet au rang de réglage, ce que le lot A du 095 vient de corriger. Les
écarts entre articles doivent venir du contenu.

**L'article est su avant de décider.** Le canal `information` s'injecte à la bascule de journée,
avant tout réveil — jamais à l'arrivée. Un test le verrouille sur l'ordre des appels, parce que
c'est la seule différence de régime entre ce canal et celui des chocs, et qu'elle est invisible à
la lecture d'une sortie.

**Une absence de matière ne produit pas un score.** Effectif minimal déclaré partout, verdict
« non concluant » en dessous. Dans ce dépôt, l'absence de mesure produit 0,0, c'est-à-dire le score
parfait.

---

## 1. Ce qui se teste sans simulateur et sans modèle

### L2 — la grille

| # | Règle | Refus attendu |
|---|---|---|
| G1 | exactement **20 cellules**, 5 articles × 4 modes | une cellule manquante ou en trop |
| G2 | `signe ∈ {+, -, 0}` et `intensite ∈ {0..3}` | toute autre valeur |
| G3 | `signe == '0'` **si et seulement si** `intensite == 0` | un signe posé sans intensité, ou l'inverse |
| G4 | `motif` non vide sur chaque cellule | une prédiction sans raison |
| G5 | l'empreinte du fichier est reproductible et figure dans tout rapport | un rapport sans empreinte |

### L1 — le corpus

| # | Règle | Refus attendu |
|---|---|---|
| C1 | `brut.txt` correspond à l'empreinte du HTML source déclarée au manifeste | un texte modifié après gel |
| C2 | `paraphrase.txt` ne contient **aucun** mot de `lexique_mobilite` | un seul mot suffit à refuser |
| C3 | `temoin.txt` n'en contient aucun non plus | un témoin qui parle de circulation n'est pas un témoin |
| C4 | longueur du témoin à ±15 % de son article | au-delà, l'appariement est perdu |
| C5 | les **30 fichiers** existent — français source et anglais gelé pour chacun des 15 textes | un fichier manquant fait échouer le chargement |
| C6 | l'entrée injectée porte la mention **« Translated from French »** | une traduction servie comme un original |
| C7 | `MANIFEST.yaml` nomme **qui** a traduit et **quand** | une traduction anonyme ne se vérifie pas |

### L4 — le canal `information`

| # | Règle | Refus attendu |
|---|---|---|
| I1 | empreinte du texte ≠ manifeste → **refus au chargement** | la garde de citation |
| I2 | consigne, verdict ou intention dans le texte → refus | marqueurs repris de `chocs.py` |
| I3 | `gravite ∉ ]0 ; 1,3]` → refus | hors du domaine que la force sait porter |
| I4 | `jour` hors de l'horizon du run → refus | une parution qui n'arrive jamais |
| I5 | règle d'exposition inconnue, ou foyer absent de la population → refus | une faute de frappe ne doit pas produire un run muet |
| I6 | **un seul lecteur par foyer**, tiré par hachage déterministe, et le tirage est journalisé | deux extractions donnent les mêmes lecteurs |
| I7 | le jour de parution se calcule sur l'**ancre du run** (`jours_ecoules`), pas sur le premier timestamp observé | après reprise à chaud, la parution ne recule pas |
| I8 | cache de décisions actif → **`[ALARME]`** | reprise de la garde des chocs |
| I9 | drapeau éteint → le run se comporte **exactement** comme avant ce ticket | comparabilité de tout ce qui a été mesuré avant |
| I10 | le refus E6 d'`experience.py` est levé pour `type: information` **seul** ; `incident` reste refusé par ce chemin | une levée trop large rouvrirait ce que le 079 a fermé |

### L5 — la mesure

| # | Règle |
|---|---|
| M1 | une ligne par `(jour, agent)` dès qu'une information est déclarée, **y compris les jours sans effet** — une abscisse qui n'existe que le jour de parution ne trace rien |
| M2 | `jour_relatif_parution` redérivé des horodatages de `informations.jsonl`, jamais d'une colonne écrite pendant le run |
| M3 | `role ∈ {lecteur, coresident, temoin}` sur chaque ligne, dérivé du tirage journalisé |
| M4 | `contrainte_chaine` renseignée ; un changement de mode concomitant **ne compte pas** comme diffusion |
| M5 | cellule vide ≠ zéro, sur toutes les colonnes de comptage |
| M6 | le module reste *fail-open* et muet quand il ne tourne pas — **et un test vérifie qu'il est appelé**, pas seulement qu'il fonctionne (leçon du 19 septembre : 42 jours sans CSV, tests au vert) |

### L3 — le dépouillement

| # | Règle |
|---|---|
| S1 | les **mêmes** déplacements sous toutes les conditions ; un écart fait échouer le scoring |
| S2 | `option_order_seed` distinct à chaque requête |
| S3 | $S_{\text{sign}}$ se calcule sur les 20 cellules gelées, et le rapport porte les deux empreintes |
| S4 | mode absent de l'échantillon → **« non concluant »**, jamais 0,0 |
| S5 | le rejeu à l'identique de C1 est **obligatoire** dans le rapport : sans lui, l'amplitude du témoin se compare à zéro |

---

## 2. Ce qui exige un run, et rien de plus

**P0 — la plomberie, 4 agents, 12 jours, ~300 requêtes.** Trois observations, toutes trois
nécessaires pour autoriser P1 :

| # | Attendu | Ce qui le falsifie |
|---|---|---|
| R1 | l'entrée `[ PRESSE ]` est servie à la **première** décision du jour de parution | elle arrive après, ou pas du tout |
| R2 | elle survit au point de reprise de 3 h et reste servie le lendemain | elle disparaît à la reprise |
| R3 | au moins un concept naît de la consolidation du soir chez le lecteur | zéro concept → **l'étage 3 n'a pas d'objet**, et P1 ne se lance pas |

---

## 3. Les prédictions, posées avant le premier run

Reprises du § 9 du ticket. Elles ne se réécrivent pas après mesure.

| # | Prédiction | Ce qui la falsifie |
|---|---|---|
| P1 | chez le lecteur, la part du mode visé s'écarte du témoin dès le lendemain de la parution, au-delà du plancher de bruit | écart dans le bruit, ou de signe contraire à la grille |
| P2 | le co-résident ne bouge **pas** avant l'ancrage du concept chez le lecteur | un co-résident qui bouge à J+1 → le canal n'est pas la mémoire |
| P3 | l'effet s'éteint plus vite chez ceux qui ont continué d'utiliser le mode visé | extinction simultanée chez évitants et persistants |
| P4 | à l'enquête, **confort et sécurité** du mode visé chutent ; rapidité, coût et **écologie** ne bougent pas | l'écologie bouge → instrument invalide, tout le reste devient illisible |
| P5 | le texte témoin ne déplace ni le comportement ni les scores déclarés | il en déplace autant que l'article → $H_3$ réfutée |
| P6 | le bras « ouï-dire » diffuse plus vite et produit plus de reformulations circulaires | pas de différence → R1 du 078 ne protège de rien |
| P7 | la divergence intra-foyer des perceptions baisse chez les exposés, l'inter-foyers non | tout le monde converge → c'est le modèle qui parle |

**Chiffre gelé pour l'étage 1 :** sur vingt prédictions, la barre du binomial est à **quinze**
signes concordants ($p = 0{,}021$) ; quatorze ne suffisent pas ($p = 0{,}058$). Si la réponse à Q4
fait passer la grille à 22 ou 23 cellules, **cette barre se recalcule avant la campagne**, jamais
après.

**Plancher de bruit à déclarer avec tout résultat :** 1 écart de mode sur 31 décisions appariées,
soit 3,2 %, mesuré le 2026-09-21 sur deux témoins et un seul persona (095 § 7 bis). C'est un ordre
de grandeur, pas un taux : trois ou quatre témoins de plus restent à jouer.
