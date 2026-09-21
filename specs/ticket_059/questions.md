# Ticket 059 — questions vivantes

Ouvert le 2026-09-21, à l'élargissement du ticket aux trois étages. Les lots 1, 2 et 6 peuvent
commencer sous les hypothèses ci-dessous ; **le lot 4 (canal `information`) ne se code pas avant
les réponses à Q1, Q2, Q5 et Q6.**

| # | Question | Hypothèse tenue faute de réponse | Ce qu'elle engage |
|---|---|---|---|
| Q1 | Constante de gravité des articles : 0,70 pour les cinq ? | oui, plus deux bras de sensibilité à 0,35 et 1,00 | la durée de l'effet, donc l'horizon de tous les runs |
| Q2 | Un seul lecteur par foyer, ou tous les membres d'un foyer exposé ? | un seul, tiré à graine fixe et journalisé | sans co-résident, l'étage 3 n'a pas d'objet |
| Q3 | Le bras « ouï-dire » (`memoire__partage_foyer_observations_min = 0`) entre-t-il dès P1 ? | oui | c'est lui qui transforme le constat « l'ouï-dire ne circule pas » en mesure |
| Q4 | Les trois cellules ambiguës de la grille : dédoublées par motif, ou « pas d'effet attendu » ? | « pas d'effet attendu », grille à vingt signes | le dénominateur du taux de signe, donc la barre du binomial |
| Q5 | Parution un jour unique, ou répétée sur plusieurs jours comme le choc C1 ? | un jour unique | une parution répétée mêle la persistance du souvenir à la répétition du stimulus |
| Q6 | Chaînage des véhicules actif partout, ou coupé dans les blocs visant la voiture ? | actif, premier article visant les TC, bras coupé si un article voiture est joué | le confondant « le lecteur libère la voiture du foyer » |
| Q7 | Cache de décisions pendant une campagne de presse ? | coupé, comme pour les chocs | la clé ne porte ni l'article ni le souvenir |
| Q8 | P0 (3 foyers, ~1 400 requêtes) est-il obligatoire avant P1 ? | oui | 1 400 requêtes pour savoir si le canal est vide, contre 43 000 pour l'apprendre trop tard |

---

## Ce qui reste à écrire avant le code

`specs/ticket_059/tests.md` — le contrat de tests, et les sept prédictions signées du § 9 du
ticket. Il s'écrit au démarrage du lot 0, une fois les questions ci-dessus tranchées, et **avant**
la première ligne de code. Les prédictions ne se réécrivent pas après mesure.

---

## Ajout du 2026-09-21, après le premier retour de l'auteur

L'auteur a écarté le run à cinq blocs comme mode de travail (« pas efficace pour du debug, coûteux
en appels si je dois itérer ») et demandé un échantillon plus petit. Le § 7.2 et le § 7.3 du ticket
sont réécrits en conséquence : un article à la fois, les blocs seulement en forme finale, et un
escalier de paliers dont chaque marche décide de la suivante.

| # | Question | Hypothèse tenue faute de réponse |
|---|---|---|
| Q9 | L'étage 1 démarre-t-il par E1-a — 200 déplacements, un article, C1 et C2, **400 requêtes** — plutôt que par la cohorte entière à 52 784 ? | oui ; E1-d (cohorte entière) ne se lance que si un relecteur l'exige ou si l'intervalle de E1-c est trop large |
| Q10 | Strates du sous-échantillon : mode de référence, motif, tranche horaire, zone de résidence ? | ces quatre, graine journalisée, et les **mêmes** déplacements pour toutes les conditions |
| Q11 | P1 à 20 agents (10 foyers de taille 2) sur 25 jours suffit-il pour donner la variance qui dimensionne P2 ? | oui, sous réserve que P0 ait montré le canal allumé |

---

## Ajout du 2026-09-21, à l'écriture du plan d'architecture

| # | Question | Hypothèse tenue faute de réponse |
|---|---|---|
| Q12 | **Les cinq articles sont français ; le dispositif est anglais depuis le 074.** Traduit-on ? | **TRANCHÉ le 2026-09-21 — on traduit, avec mention « traduit du français ».** Les deux versions sont gelées avec leurs empreintes, la traduction est faite une fois, le manifeste nomme qui l'a faite et quand, et l'entrée servie à l'agent porte la mention. `plan.md`, lot 1 |
| Q13 | « Corrige les articles » du retour de l'auteur | **TRANCHÉ le 2026-09-21 — il s'agit des chapitres du papier AAMAS**, pas du corpus de presse. Traité sous le verrou de l'article, diff présenté et accord demandé séparément |
