# Lancer les expériences du ticket 095

> Ticket : `docs/tickets/ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md`
> Contrat de tests : `specs/ticket_095/tests.md` · Questions ouvertes : `specs/ticket_095/questions.md`
> Code livré le 2026-09-21. Ce manuel décrit les **runs**, qui restent à jouer.

---

## Ce qu'on cherche à établir, en une phrase

Que **la durée d'un effet de choc est une conséquence de l'événement et non un réglage**. Tant
que cette phrase n'est pas démontrée, le chapitre 7 de l'article ne peut affirmer aucune durée
d'extinction, et un relecteur qui ouvre le dépôt trouvera que la date de retour à la voiture se
lisait dans `settings.py`.

Chaque expérience ci-dessous a une phrase à établir et une condition qui la falsifie. **Une
expérience dont on ne sait pas dire ce qui la falsifierait ne se lance pas.**

---

## Les réglages, en clair

Ce sont des variables d'environnement. Elles sont posées **devant la commande**, et l'orchestrateur
les fait entrer dans `identite_run.json` : un bras ne peut plus se confondre avec un autre après
coup.

| Variable | Valeurs | Ce qu'elle décide |
|---|---|---|
| `MEMOIRE__MODE_FENETRE_CHANGEMENTS` | `derivee` (défaut) · `fixe` | **Le cœur du ticket.** `derivee` : un souvenir de choc reste servi au modèle tant que son poids de décroissance dépasse un seuil, soit une durée qui suit sa gravité. `fixe` : coupure franche au bout de N jours, quelle que soit la gravité — c'est le comportement d'avant le 2026-09-21 |
| `MEMOIRE__FENETRE_CHANGEMENTS_JOURS` | entier, 14 par défaut | Le N ci-dessus. **Lu uniquement en mode `fixe`** |
| `MEMOIRE__SEUIL_SERVICE_CHANGEMENT` | 0,35 par défaut | Le poids sous lequel le souvenir quitte le bloc de prompt. Ne pas y toucher sans raison écrite |
| `MEMOIRE__IMPORTANCE_CHOC` | 0,70 par défaut | **Le seuil d'entrée dans le bloc.** Un souvenir moins grave que ça n'entre pas du tout. Cf. « La question du seuil » |
| `MEMOIRE__RETARD_SATURATION` | `asymptote` (défaut) · `palier` | `asymptote` : un retard au-delà de 30 min pèse plus qu'un retard de 30 min. `palier` : le comportement d'avant le 2026-09-21, où 30, 45 et 60 minutes valaient la même chose. **À déclarer `palier` pour reproduire un run antérieur** |
| `EXPERIMENT_SURVEY_ENABLED` | `0` · `1` | Active l'enquête du soir (les cinq questionnaires posés à l'agent) |
| `EXPERIMENT_SURVEY_DAYS` | `12,17,31,40` | Les jours de simulation où l'enquête est posée |
| `EXPERIMENT_SURVEY_MODES` | vide = voiture, TC, vélo, marche | Les modes interrogés. À étendre si le choc du run vise le train ou le deux-roues |
| `RUN_PARENT` / `CHAMPS_LIBRES` | vide | Runs enfants — voir « Faire jouer le socle commun une seule fois » |
| `LLM__INSTANCES_ADMISES` | table `fonction → instances` | **Posé par l'orchestrateur, ne pas surcharger.** Décision et auto-réflexion sur `gemini-3.1`, réflexion du soir et enquête sur `gemini-3.5`. Deux instances minimum par fonction : en deçà, un HTTP 503 devient un échec sec |

**⚠ Le défaut a changé le 2026-09-21.** Tout run joué avant cette date tournait en fenêtre fixe de
14 jours. **Un run archivé ne se compare à un run neuf qu'en déclarant `fixe`.**

---

## Avant le tout premier lancement — une seule fois

Le code est monté en volume dans le conteneur : **aucune image à reconstruire.** Mais les
variables d'environnement nouvelles n'entrent que par une **recréation du conteneur**. Depuis la
racine du dépôt :

```bash
make up
```

⚠ **Ne pas appeler `docker compose` sans `--project-directory`.** Les services déclarent
`env_file: ./.env`, qui se résout depuis le **répertoire de projet** et non depuis celui du
fichier compose. Lancé avec le seul `-f infra/docker-compose.yml`, compose cherche `infra/.env`,
ne le trouve pas, et s'arrête. C'est pour cela que le Makefile passe
`--project-directory <racine>` — et c'est la raison de préférer `make up`.

L'équivalent direct, si vous y tenez, et toujours depuis la racine :

```bash
docker compose -f infra/docker-compose.yml --project-directory . up -d controller
```

⚠ **`make restart` ne suffit pas** : un redémarrage relance le conteneur avec l'environnement
qu'il porte déjà. Seul `up` le recrée quand sa configuration a changé.

Puis, après le premier bras, ouvrir son `identite_run.json` et vérifier qu'il porte bien
`mode_fenetre_changements`, `seuil_service_changement`, `plancher_changement_jours` et
`plafond_changement_jours`.

**S'ils manquent, le conteneur tourne encore sur l'ancien environnement et le bras mesure autre
chose que ce qu'il déclare.** C'est exactement le défaut qui a fait tourner le premier bras de la
campagne du 19 septembre aux valeurs par défaut du dépôt.

---

## Trois règles permanentes

1. **Une seule campagne à la fois.** Une campagne recrée le conteneur `controller` et tuerait un
   run en cours. Règle posée le 2026-09-16, après que trois superviseurs se sont disputé les mêmes
   expériences et en ont perdu une.
2. **Cache de décisions coupé.** Sa clé ne porte aucune durée : une décision prise avant le choc
   pourrait être resservie pendant. L'orchestrateur le coupe déjà ; une alarme se lève si on
   l'oublie, mais elle ne corrige rien.
3. **Le chaînage des véhicules reste actif.** Réactivé le 2026-09-21. Les bras des 19 et 20
   septembre restent valables pour ce qu'ils démontrent sur la fenêtre, mais **leurs parts modales
   absolues ne sont pas citables**.

---

## E1 — Le plancher de bruit

**Objectif.** Établir que deux runs identiques donnent des décisions identiques. Sans cette
mesure, aucun écart observé ensuite n'est attribuable au choc.

**Attendu, et DÉMENTI le 2026-09-21.** L'attendu était « 0 écart de mode ». La mesure donne
**1 écart sur 31 décisions appariées, soit 3,2 %**, à température 0, graines identiques, cache
coupé. C'est le modèle qui ne rend pas deux fois la même distribution ; le tirage, lui, est
déterministe.

**Conséquence, décidée par l'auteur le 2026-09-21 :** plancher non nul **assumé et déclaré**, la
campagne continue. Un effet de choc doit dépasser ce plancher pour être attribuable — celui de
septembre allait de 95 % à 0 % de part voiture, très au-dessus. Ce qui n'est pas défendable, c'est
d'annoncer un plancher nul qu'on n'a pas.

**Reporté :** chiffrer le plancher pour de bon demande trois ou quatre témoins de plus, arrêtés à
une semaine simulée. Détail et questions ouvertes au § 7 bis du ticket.

```bash
python scripts/experiment/run_sequential_cohort.py --branch control --experiment-id e1_temoin_a
python scripts/experiment/run_sequential_cohort.py --branch control --experiment-id e1_temoin_b
```

**Ce qu'on lit après.** Comparer les `decisions_rejeu.jsonl` des deux bras, ligne à ligne sur la
clé `(personne, activité, instant)`. Les `code_plan` doivent coïncider partout.

**Le routage par fonction est déjà actif** (décision du 2026-09-21) : ce plancher est donc mesuré
sous le binding définitif, et n'aura pas à être refait. C'est la raison d'avoir tranché avant de
lancer quoi que ce soit — adopté après, il aurait obligé à le rejouer.

---

## E2 — La fenêtre dérivée reproduit la fenêtre fixe

**Objectif.** Contrôle de non-régression. Avant de faire varier la gravité, vérifier que le calcul
nouveau reproduit l'ancien comportement là où les deux devraient coïncider.

**Attendu.** Les bras « fixe 14 » et « dérivée » se comportent de façon **indiscernable jusqu'au
jour 29**, puis divergent d'environ un jour — la durée dérivée à gravité 0,70 vaut 15,29 jours
contre 14 pour la fixe.

**Ce qui falsifie.** Une courbe différente **avant** le jour 29 : le calcul est faux, pas la
théorie. Ne pas passer à E3 dans ce cas.

```bash
# Bras 1 — témoin sans choc
EXPERIMENT_SURVEY_ENABLED=1 EXPERIMENT_SURVEY_DAYS=12,17,31,40 \
python scripts/experiment/run_sequential_cohort.py --branch control --experiment-id e2_temoin

# Bras 2 — traité, fenêtre FIXE de 14 jours (le comportement d'avant)
MEMOIRE__MODE_FENETRE_CHANGEMENTS=fixe MEMOIRE__FENETRE_CHANGEMENTS_JOURS=14 \
EXPERIMENT_SURVEY_ENABLED=1 EXPERIMENT_SURVEY_DAYS=12,17,31,40 \
python scripts/experiment/run_sequential_cohort.py --branch treated --experiment-id e2_fixe14

# Bras 3 — traité, fenêtre DÉRIVÉE de la gravité
MEMOIRE__MODE_FENETRE_CHANGEMENTS=derivee \
EXPERIMENT_SURVEY_ENABLED=1 EXPERIMENT_SURVEY_DAYS=12,17,31,40 \
python scripts/experiment/run_sequential_cohort.py --branch treated --experiment-id e2_derivee
```

**Ce qu'on lit après.** Dans `app.log`, la ligne de sortie de fenêtre :

```
[noyau] 899549 : le souvenir de choc du 2026-03-31 est sorti du bloc « ce qui a changé
récemment » (durée 15.29 j dérivée d'une gravité de 0.70 (force 14.56 j, durée calculée
15.29 j)) — plus aucun souvenir de choc ne pèse sur ses décisions.
```

Elle donne la gravité **mesurée** et la date de sortie. C'est la mesure centrale de E3 : la noter.

---

## E3 — La durée suit la gravité

**Objectif.** Le cœur du ticket. Établir que la date d'extinction de l'effet **se déplace avec la
gravité de l'événement**, dans l'ordre et l'ordre de grandeur prédits.

**Attendu.** Trois bras traités en fenêtre dérivée, trois gravités croissantes, trois dates
d'extinction croissantes, à ± 1 jour des durées calculées.

**Ce qui falsifie.** Des extinctions **au même jour** malgré des gravités différentes — le calcul
n'est pas branché. Ou des extinctions **dans le désordre** — la gravité ne mesure pas ce qu'on
croit.

### La gravité se déclare, elle ne se subit pas

Elle est **entièrement décidée par la déclaration du choc**, sans le modèle :

```
gravité = part_de_retard(t)  +  0,20 × incident réseau
        + 0,20 × correspondance ratée  +  0,10 × mode contraint

part_de_retard :  t ≤ 30 min → 0,50 × t / 30 min
                  t > 30 min → 0,70 − 0,20 × exp(−(t − 30 min) / 12 min)
```

**Depuis le 2026-09-21, le retard ne sature plus à 30 minutes.** C'est ce qui rend cette
expérience possible : auparavant, 30, 45 et 60 minutes donnaient rigoureusement la même gravité,
et trois bras aux retards différents auraient produit **trois fois la même date d'extinction**.

### Le montage : un persona, un mode, trois retards

Trois variantes d'un choc voiture sur Corinne. Persona, mode, contexte et texte tenus fixes ;
seul le retard déclaré change.

| Bras | Retard déclaré | Gravité | Durée servie | Extinction attendue |
|---|---:|---:|---:|---|
| léger | **30 min** | 0,700 | **15,29 j** | ~ jour 31 |
| moyen | **45 min** | 0,843 | **17,80 j** | ~ jour 34 |
| lourd | **90 min** | 0,899 | **18,79 j** | ~ jour 35 |

Les trois franchissent le seuil d'entrée de 0,70, donc les trois produisent un effet observable —
c'est ce qui manquait tant que le retard saturait.

⚠ **Les écarts entre bras sont de deux à trois jours**, pas de dix. La gravité étant bornée à 1,
la durée servie l'est à 20,6 jours : l'amplitude totale entre le choc le plus léger qui franchisse
le seuil et le plus lourd concevable vaut cinq jours. **Un protocole qui ne sait pas dater
l'extinction au jour près ne conclura rien.** La ligne de journal de sortie de fenêtre la date
exactement — c'est elle qu'il faut lire, pas la courbe de part modale.

Préparatif : `run_sequential_cohort.py` fige le choc de référence en dur
(`CHOC_REFERENCE = "c6_voiture_suspecte"`). Il faut en faire un paramètre, ou déclarer trois
fichiers de choc dérivés. Petit changement, sans effet sur les deux premières expériences.

### Chaque choc est taillé pour la population qu'il touche

C'est le dessin voulu, et il explique pourquoi le montage ci-dessus ne mélange pas les chocs du
catalogue : chacun déclare sa règle d'exposition.

| Choc | Exposition | Retard | Gravité |
|---|---|---:|---:|
| C1 bouchon rocade | voiture, deux-roues | 60 / 25 / 12 min | 0,88 · 0,62 · 0,40 |
| C2 crevaison | tirage de 30 % des cyclistes | 35 min | 0,77 |
| C3 panne réseau | usagers des transports en commun | 45 min + corresp. | 1,00 |
| C4 train supprimé | usagers du train | 50 min | 0,86 |
| C5 orage de grêle | marche, vélo, deux-roues | 15 min | 0,45 |
| C6 moteur suspect | agents désignés, mode `car` | 30 / 20 min | 0,70 · 0,53 |

Corinne roule en voiture : seuls C1 et C6 la touchent. Faire porter C2 ou C3 sur elle ne
produirait rien — ce n'est pas une limite du code, c'est que le choc ne la concerne pas.

**Une alternative au montage ci-dessus** serait un persona par choc, chacun exposé au sien, avec
son propre bras témoin. Les gravités seraient plus écartées (0,70 à 1,00), mais persona et gravité
varieraient ensemble, et ce qu'on comparerait serait l'écart au témoin, pas la date absolue.

### La question du seuil

Les chocs les plus courants du dépôt — C1 premier jour, C2, C4, C6 — valent **exactement 0,70**, et
ne franchissent le seuil que parce que la comparaison est `>=`. Un choc voiture ne peut pas faire
mieux. Toute modification d'une pondération ferait basculer d'un coup **tous** ces chocs sous le
seuil, et l'hystérésis disparaîtrait sans qu'aucune ligne ne le dise.

Ce n'est pas théorique : le 18 septembre, le seuil est passé de 0,70 à 0,50 dans `config.yaml`,
dans la conviction que le choc ne le franchissait pas. Il le franchissait. Effet recherché : nul.
Effet obtenu : six souvenirs de plus rappelés sans condition de contexte, et une trentaine de tests
rouges. Annulé le lendemain.

Proposition en deux pièces indépendantes, détaillée dans `specs/ticket_095/questions.md` (Q3bis) :

1. **journaliser la marge au seuil** et alarmer quand elle est nulle — ne change aucun
   comportement, rend l'accident de septembre impossible à répéter en silence ;
2. **déplacer le seuil à 0,66**, au milieu de l'intervalle `]0,62 ; 0,70[` qui ne contient aucune
   valeur atteignable — ne change **aucune classification**, et porte la marge de 0,000 à 0,04 des
   deux côtés. Aucun run n'ayant encore été joué, le faire maintenant ne coûte aucune reprise.

## E4 — Le plafond de 30 jours · ABANDONNÉE

**Décision du 2026-09-21 : pas de run.** Le plafond de 30 jours est **une sécurité, pas un seuil
qu'on doit atteindre**. Il existe pour qu'un souvenir grave et souvent rappelé ne repousse pas
indéfiniment sa propre échéance dans un bloc de taille fixe ; il n'a pas à être exercé en
situation.

Il reste couvert par les tests unitaires (`test_095_lotA_duree_derivee.py`, cas A6 et B8), où une
force portée à 30 jours donne une durée calculée de 31,49 j, ramenée à 30, et la ligne de journal
nomme le plafond.

À noter pour la rédaction : la gravité étant plafonnée à 1,0, la durée maximale qu'elle peut
produire vaut **20,58 jours**. Le plafond ne mord donc jamais par la gravité — uniquement par le
renforcement au rappel. La formule citée dans le chapitre 7 porte ce plafond de 30 : un relecteur
qui fait le calcul verra qu'il est inatteignable par cette voie.

## E5 — L'enquête voit ce que le comportement montre

**Objectif.** Sortir de la seule part modale. Aujourd'hui, une part modale qui s'effondre ne permet
pas de dire si l'agent **a changé d'avis** ou seulement changé d'itinéraire.

**⚠ Ce n'est pas un run de plus.** C'est E2 et E3 joués avec `EXPERIMENT_SURVEY_ENABLED=1`.
L'activer dès E2 coûte 20 requêtes par bras sur environ 260, soit **8 %**. Rejouer E2 et E3 ensuite
pour l'obtenir coûte **100 %**. Les commandes d'E2 ci-dessus l'activent déjà.

**Attendu, par ordre de force décroissante :**

1. **Les scores de sécurité et de rapidité de la voiture chutent entre J12 et J17.** Si rien ne
   bouge alors que la part modale s'effondre, l'agent change de comportement sans changer d'avis —
   c'est un résultat publiable en soi, et cohérent avec les zéro contradictions de concept déjà
   mesurées.
2. **Le score d'écologie de la voiture ne bouge pas.** C'est la **question témoin** : aucun des six
   chocs déclarés ne vise l'écologie. Si elle bouge, l'agent a exprimé une humeur globale au lieu
   de noter un critère, **l'instrument est invalide et le reste de E5 ne s'interprète pas.**
3. **Les six critères d'un même mode ne corrèlent pas au-delà de 0,9.** Au-delà, le découpage par
   mode n'a pas suffi et il faut descendre à six questionnaires par soir.
4. **Le mode prédit par `Σ perception × priorité` coïncide avec le mode choisi le lendemain** dans
   une majorité de cas. Une divergence durable est le résultat le plus intéressant du lot, pas un
   échec.

**Ce qu'on lit après.** `affinites_declarees.csv`, une ligne par (jour, persona, mode, critère,
score). Les six priorités y sont aussi, sous `mode = critere_priorite`.

**Vérification de premier niveau, à faire au premier jalon :** ouvrir le fichier et confirmer qu'il
y a bien **cinq questionnaires** (quatre modes + priorités) et **trente lignes** par jalon. Un
jalon muet lève `[ALARME] [enquete]` dans `app.log`.

---

## Faire jouer le socle commun une seule fois

Les quatorze premiers jours des trois bras de septembre étaient identiques — 44 décisions, 0 écart
— et **payés trois fois**. Un run parent joue le socle et se fige ; chaque bras en hérite :

```bash
RUN_PARENT=<nom_du_run_parent> CHAMPS_LIBRES=choc,mode_fenetre_changements \
python scripts/experiment/run_sequential_cohort.py --branch treated --experiment-id e3_bras_1
```

`CHAMPS_LIBRES` nomme **ce que ce bras s'autorise à faire varier** par rapport à son parent. Tout
autre écart fait refuser le démarrage en citant le champ : un enfant hérite de la **mémoire** de
son parent, et une mémoire produite sous d'autres réglages décrit une autre expérience que celle
qu'il va jouer.

Au moment où l'enfant cesse de rejouer son parent, une recette compare les décisions communes et
lève `[ALARME] [filiation]` en cas d'écart. **Lire cette ligne avant d'exploiter le bras.**

Économie : environ un tiers du coût par bras additionnel. E1 n'en profite pas (pas de socle
commun) ; E2 et E3 oui.

---

## Ce qui reste à trancher

### Le montage de l'expérience sur la gravité

**Débloqué le 2026-09-21** par la suppression du palier de retard : trois retards déclarés sur le
même persona donnent désormais trois durées distinctes (15,3 / 17,8 / 18,8 jours), là où ils
donnaient trois fois la même. Détail dans la section E3. Reste à rendre le choc de référence
paramétrable dans le lanceur — petit changement, sans effet sur les deux premières expériences.

### Le seuil d'entrée à 0,70

Détaillé dans la section E3 également, et dans `specs/ticket_095/questions.md` (Q3bis). Deux pièces
indépendantes : journaliser la marge au seuil et alarmer quand elle est nulle ; et, si on le veut,
déplacer le seuil à 0,66, ce qui ne change aucune classification.

---

## Décisions déjà prises, le 2026-09-21

| Question | Décision |
|---|---|
| Attribuer des modèles différents aux fonctions de l'agent ? | **Oui, tout de suite.** Décision et auto-réflexion sur `gemini-3.1` (inchangé, c'est la variable mesurée de l'article) ; réflexion du soir et enquête sur `gemini-3.5`. Posé dans l'orchestrateur, deux instances par fonction, jamais d'épinglage dur. Comme aucun run n'a encore été joué, cela ne coûte aucune reprise |
| Faire hériter les bras d'un run parent ? | **Oui, mais pas dès le premier run.** Le plancher de bruit n'en profite pas. Construire le parent depuis le premier bras du contrôle de non-régression, une fois la recette de reproduction validée pour de vrai |
| Faire mordre le plafond de 30 jours ? | **Non.** C'est une sécurité, pas un seuil qu'on doit atteindre. Couvert par les tests unitaires, pas de run |
| Le palier de retard à 30 minutes | **Supprimé.** Au-delà de la référence, la composante de retard monte encore en décélérant, vers 0,70 sans l'atteindre. Rien ne change en dessous de 30 minutes. C'est ce qui rend l'expérience sur la gravité exécutable |
| Le troisième jalon d'enquête | **Recalé de J29 à J31.** Il avait été choisi pour tomber le jour de sortie sous fenêtre fixe de 14 jours ; en mode dérivé la sortie glisse d'environ +1,3 jour, et J29 manquerait la bascule qu'il doit montrer |

---

## Décisions de protocole du 2026-09-21, pour la campagne suivante

### L'enquête passe au quotidien

**Un questionnaire par jour simulé**, et non plus quatre jalons. Les quatre jalons établissent
l'aller-retour des opinions ; ils ne montrent pas sa forme, et l'intervalle qu'ils ne couvrent pas
est précisément celui où le récit quitte le contexte.

```bash
EXPERIMENT_SURVEY_DAYS=$(seq -s, 1 42) \
EXPERIMENT_SURVEY_MODES=voiture,transports_collectifs,velo,marche,train make run OFFLINE=1
```

Coût : six questionnaires par jour sur quarante-deux jours, soit **252 appels** contre 24, environ
**+90 % du budget d'un bras**. C'est le prix de la dynamique, et il est assumé.

### La propension quotidienne ne coûte rien et se lit déjà

À chaque décision, le modèle annonce une probabilité par mode, enregistrée dans `moves.csv`
(`P(Voiture Privée) %`…). Ce signal est quotidien, gratuit, et **ne demande aucun découpage en
phases** — donc aucune borne dérivée du paramètre dont on mesure l'effet. Sur la campagne du
2026-09-21, il chute de 90 % à 40 % le jour de l'avarie et remonte à 77 % le lendemain de la
sortie du contexte. C'est la figure du chapitre 7.

`scripts/analysis/ch7_choc_figures.py` la trace, avec les phases calées sur le choc déclaré et la
sortie calculée. `modal_variation_rate.py`, qui génère les cinq figures automatiques du run, lit ses phases
dans le run depuis le 2026-09-25 : avant / jour(s) de l'événement / après, **foyer par foyer**
depuis `evenements.jsonl` et la population, les agents hors de tout foyer exposé à part, et
« sans événement » pour un bras témoin. Titres et libellé viennent de `evenement.yaml` (ou
`choc.yaml`). Jusque-là, quatre phases étaient codées en dur sur un choc aux jours 8-9. Il ne
découpe toujours pas selon la sortie calculée du contexte, que `ch7_choc_figures.py` trace.

### Arrêt précoce sur l'extinction journalisée

Le contrôleur écrit, à l'instant exact où le dernier souvenir de choc quitte le bloc :

```
[noyau] <agent> : le souvenir de choc du <date> est sorti du bloc « ce qui a changé récemment »
(…) — plus aucun souvenir de choc ne pèse sur ses décisions.
```

**Arrêter sept jours vécus après cette ligne.** Le retour et sa stabilité sont acquis, le reste est
payé pour rien. Sur la campagne du 2026-09-21 : arrêt vers le 22 avril au lieu du 27, soit environ
12 % d'économie.

⚠ Ne pas arrêter sur un critère de stabilité de la part modale : le 11 avril affiche 5 % et le 13
en affiche 52 %, une bande étroite déclencherait au gré du bruit. L'extinction journalisée est un
événement daté, pas une statistique.

### Choisir l'événement joué

`run_sequential_cohort.py --evenement <nom>` désigne la déclaration du bras traité, cherchée dans
`config/evenements/` puis `config/chocs/`. Sans ce drapeau, c'est `c6_voiture_suspecte` — la
commande du ticket 077 rend donc le même run qu'avant.

La dérivation par persona **force `exposition.regle` à `agents`** et conserve les `modes`
déclarés : l'agent désigné n'est exposé que sur ses trajets dans ces modes. Sur une population
d'un seul habitant, laisser `regle: mode` aurait donné le bon résultat par accident, en écrivant
une déclaration qui dit autre chose que ce qu'elle fait.

⚠ **Vérifier la `cadence` avant de jouer un cas.** Non déclarée, elle vaut `trajet` : l'événement
frappe chacun des trajets éligibles de la journée. Seuls `c6` et `c3` portent `cadence: jour` ;
`c1`, `c2`, `c4` et `c5` ne l'ont pas.

⚠ **Vérifier que le persona utilise le mode exposé.** Le J16 de c6 ne s'est jamais appliqué faute
de trajet en voiture ce jour-là. Se lit dans les `moves.csv` archivés, colonne « Mode de transport
Choisi ».

**Depuis le 2026-09-22, l'orchestrateur le fait lui-même.** `run_sequential_cohort.py` prend
`--arret-sur-extinction` (et `--jours-apres-extinction`, 7 par défaut) : il lit la date simulée de
la **dernière** application de l'événement dans `evenements.jsonl`, surveille la sortie de ce
souvenir-là dans `app.log`, puis coupe. Il n'y a plus de `--souvenir-du` à recopier à la main, et
plus de surveillance à lancer à côté.

La date surveillée est celle de la **dernière** application, pas de la première : un événement à
deux jours n'est éteint que quand le second souvenir est sorti.

⚠ **Le bras traité devient plus court que son témoin.** Le témoin ne subit aucun événement
déclaré : sa trace est vide, aucune date n'est trouvée, il va jusqu'à son horizon. C'est voulu —
mais **l'analyse doit tronquer les deux bras au même jour simulé**, et ce jour est écrit dans
`arret_sur_extinction.json`, déposé dans le répertoire du run avec la date du souvenir, le nombre
de jours vécus observés et le dernier jour simulé. Ne pas le déduire de la longueur du journal.

### Le plafond d'observation : cinquante jours

Décision du 2026-09-22. Le formulaire d'expérience accepte un horizon de 1 à **50 jours**
(`HORIZON_MAX_JOURS` dans `scripts/dashboard/experiences.py`) — il valait 31 tant que la durée de
vie d'un souvenir était plafonnée à 30.

Ce n'est **pas une durée attendue** : les cinq ancres servent de 4,70 à 20,58 jours, et 31,49 au
plus quand les rappels ont porté la force à son maximum. Un run s'arrête normalement bien avant,
sur l'extinction. Cinquante jours bornent le coût du cas pathologique — un run qui ne s'éteindrait
jamais — sans rien borner de ce que le protocole mesure.

---

## Coût prévisionnel

| Poste | Requêtes par bras |
|---|---:|
| Décisions | ~122 |
| Réflexions du soir | ~105-123 |
| Auto-réflexions | 13 |
| Enquête (5 questionnaires × 4 jalons) | 20 |
| **Total** | **~260-280** |

Environ 580 000 jetons d'entrée et 80 000 de sortie par bras. Un bras met environ trois heures.
