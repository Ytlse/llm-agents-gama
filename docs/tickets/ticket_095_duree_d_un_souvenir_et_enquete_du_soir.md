# Ticket 095 — La durée d'un souvenir, et de quoi l'observer depuis l'agent

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-21. Contrat de tests à écrire **avant** le code, dans `specs/ticket_095/tests.md`.
>
> **Objet.** Faire dépendre la durée d'effet d'un événement marquant de sa gravité et non d'une
> constante ; et donner au dispositif une sonde qui mesure les croyances de l'agent, indépendamment
> de son comportement.
>
> **Reprise du ticket 048, le 2026-09-21.** Le 048 — calendrier de consolidation et échelle
> d'oubli — est **clos** : ses trois points de code sont en service depuis le 2026-09-11, et son
> reliquat est versé ici, les quatre actions de calendrier et d'oubli au **lot F** (§ 6 bis) et la
> piste des modèles locaux au **lot C** (§ 4). Les deux tickets portent le même paramètre — le
> `S0 = 2,8` du lot A **est** la constante de temps livrée par le 048.

---

## 0. Ce que ce ticket joue dans l'article AAMAS

Le chapitre 7, « Réagir à ce qu'aucune variable n'encode », porte la thèse la plus exposée du
papier : un agent à mémoire réagit à un événement qu'aucune colonne du substrat ne décrit, et
cette réaction s'éteint progressivement. C'est le chapitre qui distingue le dispositif d'un modèle
de choix discret enrichi — sans lui, il ne reste qu'un simulateur de plus.

La campagne appariée du ticket 077, jouée les 19 et 20 septembre 2026, a démontré l'effet **et**
l'a rendu inutilisable en l'état. Trois bras, même graine, même persona : témoin sans choc, traité
à fenêtre 14 jours, traité à fenêtre 7 jours. Plancher de bruit vérifié — **0 différence de mode
sur 44 décisions avant le choc**, les trois bras partent identiques. Après le choc, l'écart est
franc. Mais il s'éteint **le jour exact où le souvenir sort du bloc de prompt**, 13 avril pour le
bras à 14 jours, 6 avril pour celui à 7 jours, et pas un jour plus tard.

La phrase qui en découle — « la durée de l'effet est un paramètre de code, pas un résultat » — ne
peut pas être écrite dans un papier AAMAS. Ni tue : un relecteur qui lit le dépôt la trouvera.

Trois conséquences pour la rédaction, et ce ticket les traite dans cet ordre :

1. **La durée doit devenir une conséquence de l'événement.** Tant qu'elle est un entier posé, le
   chapitre 7 ne peut affirmer aucune durée d'extinction. C'est le lot A.
2. **L'effet doit s'observer ailleurs que dans le comportement.** Aujourd'hui la seule trace est la
   part modale ; on ne sait pas dire si l'agent a changé d'avis ou seulement d'itinéraire. C'est le
   lot B, et c'est ce qui donnerait au chapitre 7 une mesure de second ordre.
3. **Le protocole doit tenir sur les six chocs**, pas sur celui de Corinne. Un instrument réglé sur
   un moteur qui grince est aveugle à une crevaison. C'est ce qui cadre le lot B.

Les lots C, D et E sont de l'outillage : ils conditionnent le coût et la traçabilité des campagnes
que les lots A et B rendent nécessaires.

**Ce que ce ticket ne fait pas.** Il ne réécrit pas l'article. Toute écriture dans
`docs/paper/article/` reste soumise au verrou, et les signalements d'impact se font à la fin de
chaque lot, pas au fil de l'eau.

---

## 1. Le constat mesuré

Campagne `experiments/runs/ticket077_v3` et `ticket077_v3_fenetre7`, persona 899549 (Corinne),
choc C6 (moteur suspect) aux jours 15 et 16, horizon 42 jours calendaires.

| Phase | Témoin | Traité f14 | Traité f7 |
|---|---:|---:|---:|
| J1-J14 (avant choc) | — | **0 écart / 44 décisions** | **0 écart / 44 décisions** |
| J22-J28 (phase discriminante) | 95 % voiture | **0 %** | **80 %** |

Trois faits établis, tous trois à traiter :

**La durée est une constante.** Les lignes de sortie de fenêtre tombent au jour près sur
`memoire__fenetre_changements_jours`. La décroissance du souvenir — `force = 2,8 × (1 + 6 × gravité)`,
soit 14,6 jours pour une gravité de 0,70 — existe dans le code et **n'est pas consultée** par le bloc
« Ce qui a changé récemment ». Que 14,6 tombe près de 14 est une coïncidence qui a masqué le défaut :
les deux explications prédisaient la même date. Le bras f7 les a séparées.

**La mémoire empile sans réviser.** Zéro contradiction de concept dans les trois bras. La croyance
pro-voiture reste à 17-18 observations après quatorze jours sans voiture. Rien n'observe une absence :
seuls les trajets effectués produisent des observations.

**Le retour est progressif et incomplet.** P(voiture) remonte de 38,8 % à 80 %, contre 95 % au témoin.
Le choc laisse une trace permanente — c'est le résultat le plus intéressant de la campagne, et il est
aujourd'hui indissociable de l'artefact de fenêtre.

Figure : `scripts/analysis/figure_fenetre_choc.py`, sortie sous `docs/traces/2026-09-21_figure_fenetre_choc/`.

---

## 2. Lot A — La fenêtre de nouveauté pilotée par la gravité, et plafonnée

### Règle

Un souvenir de choc est servi dans le bloc « Ce qui a changé récemment » tant que son poids de
décroissance dépasse un seuil, la durée obtenue étant bornée des deux côtés :

```
poids(t)  = exp(-t / force)          force = S0 × (1 + k × gravité),  S0 = 2,8  k = 6  (plafond 30 j)
duree     = force × ln(1 / SEUIL)
servi     = PLANCHER ≤ duree ≤ PLAFOND
```

Réglages proposés : `SEUIL = 0,35`, `PLANCHER = 2 jours`, `PLAFOND = 30 jours`.

**`S0` n'est pas un nombre neuf.** C'est `long_term_retrieval__force_base_jours`
(`settings.py:534`, lu par `llm/gravite.py:232`), la constante de temps EN JOURS livrée par le
**ticket 048** le 2026-09-11, en remplacement de `memory_decay_lambda` — un paramètre déclaré
dans `experiments.yaml` et lu par aucun code. Sa valeur de 2,8 jours reproduit à 1e-3 l'ancienne
base d'exponentielle de 0,7, demi-vie de 1,94 jour comprise, précisément pour qu'aucun écart
mesuré après ce changement ne vienne d'un oubli silencieusement accéléré. Le lot A la reprend
telle quelle et ne fait que la moduler par la gravité.

Le ticket 048 est **clos le 2026-09-21** ; son reliquat est repris ici — les quatre actions de
calendrier et d'oubli au **lot F** (§ 6 bis), la piste des modèles locaux au **lot C** (§ 4).

| Gravité | Exemple | force | durée servie |
|---:|---|---:|---:|
| 0,10 | contrariété | 4,5 j | 4 j |
| 0,30 | incident mineur | 7,8 j | 8 j |
| 0,37 | C1 jour 3 | 9,0 j | 9 j |
| **0,70** | **C6, C1 jour 1** | **14,6 j** | **15 j** |
| 0,90 | C3 panne réseau | 17,9 j | 19 j |
| 1,00 | accident | 22,4 j | 23 j |
| ≥ 1,30 | — | 28,0 j | **30 j** (plafond) |

### Pourquoi un plafond est nécessaire, et pas seulement prudent

Deux raisons, l'une et l'autre vérifiables dans le code :

- **Le rappel renforce la force du souvenir** (mécanique MemoryBank, déjà implémentée). Un souvenir
  servi est un souvenir rappelé : sans plafond, un choc grave repousse indéfiniment sa propre
  échéance.
- **Le bloc est de taille fixe** — `memoire__changements_max = 3`. Un souvenir bloqué occupe une place
  que les suivants ne prennent plus : la fenêtre cesse d'être une fenêtre et devient une archive.

Le plafond de 30 jours n'est pas un nombre neuf : c'est déjà le plafond de `force` dans le code. Le
poser explicitement rend la borne lisible au lieu de la laisser émerger d'un calcul.

### Travail

- `llm/noyau.py` — `bloc_changements` consulte le poids du souvenir au lieu de compter les jours.
- `settings.py` — `memoire__seuil_service_changement` (0,35), `memoire__plancher_changement_jours` (2),
  `memoire__plafond_changement_jours` (30). `memoire__fenetre_changements_jours` est **conservé** :
  il devient le mode « fenêtre fixe », utilisé par les bras de contrôle méthodologique.
- Le mode en vigueur entre dans `identite_run.json` (ticket 091) et dans le passe-plat compose.
- La ligne de sortie de fenêtre journalise désormais **la durée calculée et la gravité qui la produit**,
  pas seulement la date.

### Ce qui reste hors périmètre

Le lot A ne corrige **pas** l'empilement sans révision. Adam & Gaudou (2025) traitent ce point par une
fenêtre glissante sur les 100 derniers trajets, dont la fréquence décroît par simple non-usage ; notre
compteur d'observations, lui, ne décroît jamais. C'est un chantier distinct, à ouvrir après mesure des
effets du lot A — le traiter en même temps rendrait les deux effets inséparables.

---

## 3. Lot B — L'enquête du soir, alignée sur Adam & Gaudou

### Le défaut à corriger d'abord

L'enquête existe depuis le ticket 077 et **n'a jamais tourné** : les quatre variables `EXPERIMENT_*`
n'étaient pas déclarées dans `infra/docker-compose.yml` (corrigé le 2026-09-21). Mais le passe-plat ne
suffit pas, parce que le prompt lui-même est vide de contexte. Dans `enquetes.py`, la perception servie
au modèle tient en quatre champs :

```python
perception_text = f"Name: {name}\nAge: {age}\nGender: {gender}\nOccupation: {occupation}\n"
```

Ni mémoire, ni habitudes, ni concepts, ni bloc de changements récents, ni modes disponibles, ni
historique. **Telle qu'écrite, l'enquête mesure l'a priori du modèle de base sur une femme de 53 ans
à temps partiel** — identique au jour 12 et au jour 29, identique dans le bras f7 et dans le bras f14.
Elle n'aurait rien détecté, et son silence aurait été pris pour une absence d'effet.

### Étanchéité en sortie, fidélité en entrée

Ce sont deux exigences distinctes, et le module n'en portait qu'une :

- **En sortie, étanchéité absolue** — la réponse n'entre ni en STM, ni en LTM, ni dans ChromaDB, ni
  dans la passerelle de réflexion nocturne. Elle va dans `affinites_declarees.csv` et nulle part
  ailleurs. C'est ce que la docstring du module promet déjà, et cela ne change pas.
- **En entrée, fidélité complète** — le prompt sert **exactement le même bloc mémoire que le prompt de
  décision** : `memoire_noyau(journal, entrees, maintenant, person_id)`, c'est-à-dire « Mes habitudes »,
  « Ce que je sais » et « Ce qui a changé récemment », plus l'identité complète du persona (âge,
  situation, ménage, revenu, motifs habituels, abonnement TC, véhicules disponibles).

Sans cette seconde exigence, la sonde ne mesure pas l'agent ; elle mesure le modèle.

### Les six critères, et pourquoi tous les six

Les critères sont ceux d'Adam & Gaudou (2025) : **rapidité, praticité, confort, sécurité,
accessibilité financière, écologie**, notés sur une échelle de Likert 0-10, comme dans leur enquête.

Les six chocs déclarés du dépôt ne frappent pas les mêmes dimensions, et c'est ce qui interdit de
tailler l'instrument sur le cas de Corinne :

| | Choc | Exposition | Critères attaqués |
|---|---|---|---|
| C1 | Bouchon majeur sur la rocade, 3 jours décroissants | voiture, 2-roues motorisés | rapidité, praticité |
| C2 | Crevaison, vélo poussé à pied | vélo, tirage 30 % | praticité, confort, sécurité |
| C3 | Panne du métro, tunnel évacué, correspondance ratée | transports en commun | rapidité, praticité, confort, sécurité |
| C4 | Train régional supprimé, 50 min sur un quai à découvert | train | rapidité, confort |
| C5 | Orage de grêle en plein air | marche, vélo, 2-roues | confort, sécurité |
| C6 | Moteur suspect, panne sur voie rapide | voiture, agents nommés | rapidité, sécurité |

Retirer la sécurité aurait rendu l'instrument aveugle à quatre chocs sur six.

**L'écologie est la question témoin.** Aucun des six chocs ne la fait bouger. Si le score d'écologie
du vélo chute après une crevaison, l'agent n'a pas noté un critère : il a exprimé une humeur globale,
et l'instrument entier est invalide. Une question qui doit rester plate est une garde, pas une dépense.

### Le découpage : un prompt par mode

Les 24 scores demandés dans un seul prompt produisent une grille plate — le modèle note la voiture à 9
partout et le bus à 3 partout, et on a payé 24 nombres pour en obtenir 4. **Un prompt par mode, le mode
nommé, les trois autres jamais cités** : l'agent note en absolu, il ne peut plus arbitrer entre modes
dans un même souffle.

Les six questions, posées à l'identique pour chaque mode, avec ancrage verbal 0/5/10 répété chaque soir
pour que l'échelle ne dérive pas d'un jalon à l'autre :

| # | Critère | Question sur `{mode}` | 0 / 5 / 10 |
|---|---|---|---|
| 1 | Rapidité | Pour tes trajets habituels, dans quelle mesure le `{mode}` te fait-il arriver vite ? | très lent / correct / très rapide |
| 2 | Praticité | Dans quelle mesure te facilite-t-il la vie — horaires, détours, bagages, imprévus ? | très contraignant / acceptable / très pratique |
| 3 | Confort | Dans quelle mesure un trajet en `{mode}` est-il agréable, sans fatigue ni tension ? | pénible / neutre / agréable |
| 4 | Sécurité | Dans quelle mesure te sens-tu en sécurité pendant un trajet en `{mode}` ? | pas du tout / moyennement / parfaitement |
| 5 | Accessibilité financière | Dans quelle mesure ce qu'il te coûte est-il supportable dans ton budget ? | insupportable / acceptable / indolore |
| 6 | Écologie | Dans quelle mesure le `{mode}` te paraît-il respectueux de l'environnement ? | très polluant / moyen / très propre |

Six entiers par prompt, **une seule** phrase de justification pour le bloc entier — une par question
multiplie la broderie par six. Température 0,2.

Modes interrogés : les quatre d'Adam & Gaudou (voiture, transports en commun, vélo, marche) par défaut,
étendus au train et au deux-roues motorisé quand le choc du run les vise (C4, C5). Liste déclarée, pas
codée en dur.

### Le cinquième prompt : les priorités

Leur questionnaire a deux vecteurs, et le second manquait à ma première proposition. Indépendamment de
tout mode :

> « Dans tes choix de déplacement quotidiens, quelle importance accordes-tu à chacun de ces six
> aspects ? » — rapidité, praticité, confort, sécurité, coût, écologie. Likert 0-10.

Non redondant par construction : les quatre premiers prompts donnent les 24 perceptions `val(m,c)`,
celui-ci donne le vecteur de poids `prio(c)`. Ensemble, ils rendent calculable la formule d'Adam &
Gaudou pour notre agent, chaque soir de jalon :

```
score(mode) = Σ  val(mode, critère) × prio(critère)
             critères
```

On obtient le mode que **leur modèle symbolique prédirait à partir des déclarations de notre agent**,
à confronter au mode qu'il choisit réellement le lendemain. Une divergence durable entre les deux
signifierait que les perceptions déclarées ne pilotent pas le comportement — ce serait le résultat le
plus fort du ticket, et il s'obtient sans rien inventer.

### Ce que le ticket ne mesurera pas

Deux sondes ont été écartées le 2026-09-21, et la section des limites du papier doit le dire :

- **La préférence déclarée tous modes en concurrence** (répartir 100 points entre les quatre modes) :
  jugée redondante avec les prompts de perception. Conséquence : la dissociation entre croyance et
  comportement se lira sur les courbes de perception face aux parts modales, ce qui est moins direct
  qu'une intention déclarée.
- **Le rappel libre** (« que te rappelles-tu de tes déplacements des deux dernières semaines ? ») :
  écarté. Conséquence : la sortie de fenêtre reste observable depuis le journal, pas depuis l'agent.

Aucune comparaison aux 650 répondants humains d'Adam & Gaudou n'est prévue : hors périmètre, et le
mélange des deux populations ferait dériver l'analyse.

### Travail

- `enquetes.py` — cinq prompts par jalon, bloc mémoire complet en entrée, ancrages, schéma de sortie.
- Nouveau format `affinites_declarees.csv` : une ligne par (jour, persona, mode, critère, score), plus
  les six priorités en lignes `critere_priorite`. Format long, pas 24 colonnes.
- Schéma JSON et gabarit de la catégorie `enquete_affinite` dans la passerelle.
- Alarme `[ALARME] [enquete]` si un jalon passe sans réponse, ou si une réponse sort du domaine 0-10.

---

## 4. Lot C — Un modèle par fonction

### Ce qui existe déjà

La plomberie est complète : `LLMRequest` porte `force_provider` et `instances_admises`, tous deux
traversant `api/routes.py`, `config/settings.py` et `worker/task_worker.py`. Ce qui manque tient en un
endroit — l'appelant lit **une liste globale unique** :

```python
# llm_agent.py:561
instances_admises=list(settings.llm.instances_admises or []),
```

C'est pourquoi les 751 requêtes de la campagne sont toutes parties sur Gemini 3.1 : le run se restreint
lui-même, volontairement (ticket 085, comparabilité).

### Règle

`settings.llm.instances_admises` accepte, en plus d'une liste plate, une table `catégorie → instances`.
La liste plate reste le défaut et le repli pour toute catégorie non nommée.

**Jamais `force_provider`.** `task_worker.py:263` ne retente que si `force_provider is None` : un
épinglage dur supprime le repli. Les quatorze `HTTP 503 high demand` de la campagne sont passés
précisément parce qu'il restait une seconde clé. Donc liste blanche de deux instances minimum par
fonction.

### Répartition proposée

Profil mesuré sur les deux bras propres (498 requêtes) :

| Catégorie | Part des jetons d'entrée | in / out par requête | Enjeu |
|---|---:|---|---|
| `itinary_multi_agent` | 46 % | 2 109 / 282 | **la variable mesurée de l'article** |
| `stm_reflection` | 46 % | 2 246 / 319 | texte libre |
| `ltm_self_reflection` | 7 % | 3 157 / 265 | rare (13/run), fort enjeu |

- décision + auto-réflexion LTM → `[google_gemini31_key1, google_gemini31_key2]`, inchangé ;
- réflexion STM + enquête du soir → `[google_gemini35_key1, google_gemini35_key2]`.

Plafond journalier porté de 1 000 à 2 000 requêtes, et les deux moitiés cessent de se disputer la même
clé — déterminant dès qu'on quitte le persona unique.

### L'avertissement qui va avec

Ce n'est **pas** un réglage d'infrastructure. Changer le modèle des réflexions STM change le contenu de
la mémoire, donc les décisions. Le binding entre dans `identite_run.json`, se gèle avant la campagne,
et reste identique dans tous les bras — sinon l'écart mesuré n'est plus attribuable au choc. Son
adoption impose de refaire le plancher de bruit (lot A de l'expérience E1 ci-dessous).

Pour un run à un persona, le gain de débit est nul : 261 requêtes en trois heures, soit 10 % du plafond
RPM d'une seule clé. Le lot se justifie par l'appariement enjeu/coût et par les populations à venir,
pas par la charge d'aujourd'hui.

### La piste des modèles locaux, sous condition de mesure — repris du ticket 048

Huit modèles LM Studio sont déclarés dans `config/llm_gateway/providers.yaml`, hors rotation
depuis le 2026-09-08. Le lot C leur ouvre une porte qui n'existait pas : dès lors que les
instances admises se déclarent par catégorie, une catégorie peut viser du local sans que la
décision y touche. Deux raisons de fond rendent la **réflexion** candidate, là où la décision ne
l'est pas.

1. **La nature de la tâche.** Une réflexion est un résumé et une extraction sous schéma
   contraint — le registre où un petit modèle local est le plus compétitif. Une décision est une
   répartition de préférence entre itinéraires : c'est *la grandeur que l'article mesure*, et
   elle ne se délègue pas.
2. **Le volume.** Les réflexions STM pèsent 46 % des jetons d'entrée (§ 4, tableau de profil).
   Les déplacer vers le local divise par deux la consommation distante sans toucher à ce qui est
   mesuré.

**Mais la réflexion produit la mémoire, qui nourrit la décision.** Une réflexion dégradée dégrade
la décision indirectement. Le principe de non-dégradation scientifique du dépôt interdit donc
d'admettre un modèle local sur une intuition, et l'avertissement ci-dessus vaut a fortiori : un
changement de modèle de réflexion **oblige à refaire E1**.

**Protocole d'admission, sur jeux gelés, sans aucun run de simulation.** Rejouer *N* prompts de
réflexion réels extraits d'un run archivé, à travers le modèle de référence et le candidat local,
puis comparer :

- taux de sorties conformes au schéma, et taux de relances ;
- nombre de concepts extraits, et accord sur le **niveau nommé** attribué ;
- accord sur la normalisation des quatre axes ;
- **et surtout l'effet en aval** : injecter les deux mémoires produites dans le *même* prompt de
  décision, et comparer les distributions de probabilité modale.

Le candidat est admis si et seulement si l'écart en aval tient dans la marge d'équivalence.
Sinon il est écarté et la réflexion reste distante. **Aucune admission « parce que c'est moins
cher ».** Conclusion possible : aucun candidat admis — c'est un résultat, pas un échec.

Contraintes connues, mesurées à la mise en service du 2026-09-08 : LM Studio refuse
`json_object` et exige `json_schema` ; un seul modèle local est chargé à la fois, donc la cascade
ne provoque pas de chargement à la volée ; le contexte par défaut est de 4 096 jetons, à porter à
16 384 via `make lmstudio-charger`.

---

## 5. Lot D — Le socle commun, en runs enfants

Les quatorze premiers jours sont identiques dans les trois bras : 44 décisions, 0 écart. Elles sont
aujourd'hui **payées trois fois**.

Option retenue le 2026-09-21 : **runs enfants**. Un run parent joue la baseline jusqu'à la veille du
choc et se fige ; chaque bras démarre depuis ce point de reprise, avec son propre réglage. Les
mécanismes existent — points de reprise (`population_1_checkpoint_*.json`), reprise à chaud
(`make run OFFLINE=1 CONT=1`), identité de run (ticket 091).

Ce qu'il reste à écrire : la filiation dans `identite_run.json` (champ `run_parent`), le refus de
démarrer un enfant dont le parent porte des réglages incompatibles, et la vérification que le rejeu
d'un enfant reproduit le parent à la décision près sur les jours communs.

Économie attendue : ~45 décisions et ~40 réflexions par bras additionnel, soit environ un tiers du coût
d'un bras.

---

## 6. Lot E — Le modèle journalisé par décision

Demande du 2026-09-20. `llm_exchanges.jsonl` porte déjà `provider` ; le journal applicatif, non. Une
décision lue dans `app.log` ne dit pas quel modèle l'a produite, et il faut recouper deux fichiers
pour l'établir.

Travail : la ligne de décision journalise `provider` et `model`. Idem pour la réflexion nocturne,
l'auto-réflexion et l'enquête. Coût nul, valeur de traçabilité immédiate — c'est la reconstitution
d'une exécution après coup.

---

## 6 bis. Lot F — Le calendrier de consolidation et l'échelle d'oubli — repris du ticket 048

Le ticket 048, ouvert le 2026-09-11 et **clos le 2026-09-21**, a livré trois points de code le
jour même de son ouverture : le plancher journalier de consolidation à 22 h
(`settings.py:497-498`, branche « plancher » de `simulation_controller.py:1654`), l'abandon de la
normalisation min-max au profit de valeurs absolues (`longterm.py:862`), et la constante de temps
d'oubli en jours (`settings.py:534`) — 15 tests dans `test_048_calendrier_et_oubli.py`. Ce qui
suit est ce qu'il n'a pas exécuté, versé ici parce que le lot A repose sur le même paramètre et
que les campagnes E2/E3 sont les runs GAMA que ce reliquat attendait.

### F1 — Mesurer le taux réel d'entrées par agent-jour, puis trancher le régime

Le 048 a retenu le **plancher journalier**, sans pouvoir le vérifier : au 2026-09-11 aucun run
n'était exploitable pour compter les entrées par agent-jour. Le seul run portant de vraies
observations GAMA était antérieur à la cohorte v5, et les runs récents sont des exécutions hors
simulateur — une entrée par déplacement, aucune observation.

La grandeur de référence est l'**appel mémoire par déplacement**, seule indépendante de la
population et de l'horizon, auto-réflexion longue durée comprise :

| Régime | Appels mémoire par déplacement | Écart sur le total |
|---|---:|---:|
| Seuil volumétrique de 10, avant le 048 | 0,69 | référence |
| **Plancher journalier — régime retenu** | **0,69 à 0,96** | **0 à +16 %** |
| Une réflexion par jour simulé, seule | 0,33 | −22 % |
| Une réflexion par déplacement | 1,05 | +22 % |

Deux lectures contre-intuitives, à conserver telles quelles : le régime « une par jour » pris
seul coûte **moins** cher qu'un seuil volumétrique, qui déclenche déjà deux consolidations
quotidiennes pour un agent mobile ; et le plancher journalier est presque gratuit, sa borne haute
supposant que *tous* les agents en ont besoin chaque jour, ce qui est faux.

**Ce qui reste à faire :** compter les entrées par agent-jour sur une campagne E2/E3, situer la
valeur réelle dans la fourchette 0,69-0,96, et confirmer ou infirmer le plancher journalier face
au régime par déplacement. Coût nul : la mesure se lit dans un run déjà payé.

### F2 — La garantie « avant le réveil » sous le volume mesuré

Le plancher ajoute des réflexions en fin de journée simulée, là où l'échéance EDF reste le réveil
de l'agent. Vérifier, une fois F1 chiffré, que la garantie tient encore et que la contre-pression
prédictive reste faisable. Tant que le volume n'est pas mesuré, la vérification n'a pas d'objet.

### F3 — Rejouer les mesures publiées qui dépendaient de la min-max

La normalisation min-max par composante rendait l'ordre par ancienneté **invariant** au paramètre
d'oubli : le souvenir le plus récent valait toujours 1, le plus ancien toujours 0, quel que soit
l'écart réel. Deux décisions n'étaient donc pas comparables entre elles. Sa suppression change le
classement des souvenirs servis, donc tout chiffre publié avant le 2026-09-11 qui en dépend.
Recenser ces chiffres et les rejouer, ou les marquer comme datés.

### F4 — Convertir les déclarations d'expériences

`experiments.yaml` déclare encore, pour le bras `exp_04a`
(`docs/paper/methode/experience_plan/experiments.yaml:389-390`) :

```yaml
memory_horizon_days: 5
memory_decay_lambda: 0.4
```

**Aucun code ne lit ces deux clés.** Le bras de sensibilité λ ÷ 3 ayant été supprimé au ticket
071 (§ 2.6, issue C), il ne s'agit plus de rendre un bras exécutable : il s'agit qu'une fiche
d'expérience cesse de déclarer un réglage que le run n'applique pas. Convertir vers
`long_term_retrieval__force_base_jours` selon `S = 1 / λ`, soit **2,5 jours** pour ce bras, et
faire de même pour l'horizon de mémoire.

⚠ **C'est le point que l'article cite.** Le chapitre 7 FR, § des manques d'avant-campagne,
point 6, écrit que « le ticket 048 déclare bloquer l'expérience tant que ces déclarations n'ont
pas été converties ». La phrase désigne désormais ce lot — signalement d'impact à rendre, pas de
réécriture sans le verrou.

### Ce qui n'est pas repris

La piste des modèles locaux du 048 n'est pas dans ce lot : elle est au **lot C** (§ 4), dont elle
est la suite naturelle une fois les instances admises déclarées par catégorie.

---

## 7. Les expériences à mener

Toutes sur le persona 899549 (Corinne), choc C6, horizon 42 jours calendaires, mêmes graines, chaînage
des véhicules **actif** (réactivé le 2026-09-21 — les bras des 19 et 20 septembre restent valables pour
ce qu'ils démontrent sur la fenêtre, mais leurs parts modales absolues ne sont pas citables).

**Ces runs portent aussi la mesure du lot F1.** Ce sont des runs GAMA courants sur cohorte v5,
donc les premiers à permettre le comptage des entrées par agent-jour que le ticket 048 attendait
sans pouvoir le prendre. Le relevé se fait sur les journaux d'un bras déjà payé, et il tranche le
régime de consolidation : à inscrire comme sortie attendue de E2, au même titre que les courbes.

### E1 — Plancher de bruit, à refaire

Deux bras témoins identiques, graines identiques, aucun choc. **Attendu : 0 écart de mode sur les
décisions.** Un seul écart invalide toute la campagne qui suit.

À rejouer obligatoirement si le lot C est adopté, puisqu'il change le modèle des réflexions.

### E2 — La fenêtre dérivée reproduit la fenêtre fixe · OPTIONNELLE

⚠ **Rendue optionnelle le 2026-09-21** (décision de l'auteur). Le bras « fenêtre fixe 14 » est un
contrôle de non-régression : il vérifie que le calcul nouveau reproduit l'ancien comportement là
où les deux devraient coïncider. La campagne du 2026-09-21 a montré la sortie du bloc à la date
que la gravité prédit, et cette date se lit dans le journal avec la force et la gravité qui la
produisent — le calcul est donc vérifié par la trace, sans second bras. À jouer si l'on veut la
comparaison de courbe à courbe ; à laisser si le budget va ailleurs.


Trois bras : témoin sans choc · fenêtre fixe 14 jours · fenêtre dérivée (seuil 0,35). Gravité du choc
C6 : 0,70, donc durée calculée 15 jours.

**Attendu :** les bras « fixe 14 » et « dérivée » se comportent de façon indiscernable jusqu'au jour 29,
puis divergent d'un jour. C'est le contrôle de non-régression : si la dérivée produit une courbe
différente, le calcul est faux, pas la théorie.

### E3 — La durée suit la gravité

Le cœur du ticket. Trois bras traités, **à fenêtre dérivée**, avec trois chocs de gravités distinctes :
C2 (crevaison, gravité faible), C6 (moteur, 0,70), C3 (panne réseau, 0,90).

**Attendu :** la date d'extinction de l'effet se déplace avec la gravité, dans l'ordre et l'ordre de
grandeur prédits par `force × ln(1/0,35)` — environ 8, 15 et 19 jours. La prédiction est posée **avant**
le run et s'écrit dans `specs/ticket_095/tests.md`.

**Ce qui falsifierait :** des extinctions au même jour malgré des gravités différentes (le calcul n'est
pas branché), ou des extinctions dans le désordre (la gravité ne mesure pas ce qu'on croit).

⚠ **E3 ET E4 SONT DÉPLACÉES PAR LA DÉCISION D7 DU TICKET 100 (2026-09-22).** Leur protocole
repose sur une prémisse qui n'est plus vraie : que la gravité d'un choc se **déclare**, par son
retard et ses composantes, et que trois chocs de sévérités mesurées distinctes produisent trois
durées de vie distinctes. Depuis D7, la gravité d'une entrée d'événement est **l'estimation de
l'agent**, et le fait mesuré n'en est plus le plancher.

Conséquence directe : déclarer C2, C6 et C3 ne garantit plus 8, 15 et 19 jours. Si l'agent juge
les trois « génant », les trois vivent **la même** durée, et le run ne falsifierait pas la
théorie — il mesurerait le jugement. Trois sorties, à trancher avant de lancer quoi que ce soit :

1. **Jouer E3 et E4 sous `jugement: aucun`**, qui est désormais le seul chemin par lequel la
   gravité déterministe qualifie une entrée. Le protocole d'origine tient alors mot pour mot —
   mais il mesure un dispositif qui n'est plus celui des campagnes de l'article.
2. **Réécrire l'attendu** : ce n'est plus « la durée suit la gravité déclarée » mais « la durée
   suit la gravité **jugée** », et la prédiction se pose sur l'intensité que l'agent rend, lue
   dans `evenements.jsonl`. C'est une expérience différente, et sans doute plus intéressante.
3. **Les retirer**, si le chapitre n'en a plus besoin.

Tant que ce n'est pas tranché, **E3 et E4 ne se lancent pas** : elles coûteraient du quota pour
mesurer une prémisse caduque.

**TRANCHÉ LE 2026-09-22 — sortie 2 : E3 se rejoue sur la gravité JUGÉE.** La gravité est celle
de l'agent, et la prédiction se pose sur l'intensité qu'il rend. Deux conditions posées avec la
décision : un **garde-fou en amont** (grille d'attendus déclarée avant de voir les réponses, la
campagne ne part pas si le jugement sort de la plage) et la **variation par profil mesurée**
plutôt que corrigée. Détail et forme proposée : `specs/ticket_095/expose_duree_d_un_souvenir.md`,
§ 6. E4 reste ouverte, sa question est reformulée au § 7 du même document.

⚠ **DÉFAUT ANTÉRIEUR À D7, trouvé le 2026-09-22 :** C2, C6 et C3 tels qu'ils sont déclarés
donnent des gravités mesurées de 0,768 / 0,700 / 1,000, soit des durées servies de
**16,5 / 15,3 / 20,6 jours**. C2, censé être le cas faible, arrive à un jour de C6 — la part du
retard est fortement concave (30 min → 0,50 ; 45 min → 0,64 ; 60 min → 0,68). Le protocole
d'origine ne produisait donc **déjà pas** l'attendu 8 / 15 / 19, avec ou sans D7. Les trois
déclarations sont à revoir avant tout run, quelle que soit la sortie retenue.

**MESURE DU 2026-09-22, APRÈS-MIDI — elle change l'arbitrage sans le trancher.** Le banc
fonctionnel du ticket 100 a d'abord donné « l'agent répond `anodin` à tout », ce qui aurait
condamné la sortie 2. C'était un défaut : le texte de l'événement n'atteignait pas le modèle.
Corrigé, B1 et B3 rejoués sur Groq donnent, sur 38 appels sans une seule réponse vide :

| Ce qu'on craignait | Ce qui est mesuré |
|---|---|
| un seul échelon pour tout | **trois** échelons — `notable` ×8, `anodin` ×5, `genant` ×2 |
| un jugement instable d'un appel à l'autre | **4/4 identiques** sur deux événements, amplitude **0 jour** |
| l'agent minore le fait mesuré | c6 mesuré à 0,53 → jugé **`grave`** (0,75), écart **+0,22** |

Durées SERVIES qui en découlent : **4,70 / 8,23 / 11,76 / 16,17 jours** — la force de l'oubli
(4,48 / 7,84 / 11,20 / 15,40 j) multipliée par `ln(1/0,35) = 1,0498`. L'étalement que E3
attendait (≈ 8, 15, 19) existe donc dans le jugement, sur cinq articles et trois personas.

Ce que cela ne dit pas : que la sortie 2 est jouable telle quelle. Le jugement est reproductible
**à texte identique** ; rien ne dit encore qu'il l'est d'un agent à l'autre ni d'un jour à
l'autre dans un run, et c'est exactement ce dont dépend une date d'extinction. Trace :
`docs/traces/banc_fonctionnel_100/BILAN.md`, section « Ce que la cause a changé ».

### E4 — Le plafond mord

Un bras avec un choc de gravité ≥ 1,30. **Attendu :** l'effet s'éteint à 30 jours et pas au-delà, et la
ligne de journal nomme le plafond comme cause. Sans ce bras, le plafond est du code non exercé.

### E5 — L'enquête voit ce que le comportement montre

Bras E2 et E3 rejoués avec `EXPERIMENT_SURVEY_ENABLED=1`, jalons J12 / J17 / J29 / J40.

**Attendu, par ordre de force :**

1. **Le score de sécurité et de rapidité de la voiture chute entre J12 et J17.** Si rien ne bouge alors
   que la part modale s'effondre, l'agent change de comportement sans changer d'avis — un résultat
   publiable en soi, et cohérent avec les 0 contradictions de concept déjà mesurées.
2. **Le score d'écologie de la voiture ne bouge pas.** Question témoin. S'il bouge, l'instrument est
   invalide et le reste de E5 ne s'interprète pas.
3. **Les six critères d'un même mode ne corrèlent pas au-delà de 0,9.** Test de colinéarité à passer sur
   la matrice complète. Au-delà, le découpage par mode n'a pas suffi et il faut descendre au critère,
   à six prompts par soir.
4. **Le mode prédit par `Σ val × prio` coïncide avec le mode choisi le lendemain** dans une majorité de
   cas. Une divergence durable est le résultat le plus intéressant du lot, pas un échec.
5. **Le bras f7 et le bras f14 divergent sur les scores déclarés au J29**, et pas seulement sur les parts
   modales. C'est ce qui prouverait que la fenêtre agit sur la croyance et pas seulement sur l'action.

### Coût prévisionnel

| Poste | Requêtes / bras |
|---|---:|
| Décisions | ~122 |
| Réflexions STM | ~105-123 |
| Auto-réflexions LTM | 13 |
| Enquête (5 prompts × 4 jalons) | 20 |
| **Total** | **~260-280** |

Environ 580 000 jetons d'entrée et 80 000 de sortie par bras. Onze bras au programme (E1×2, E2×3,
E3×3, E4×1, E5 en réutilisant E2/E3) : compter **~3 000 requêtes** et 6,5 M jetons d'entrée.

Avec le lot D (runs enfants), l'économie porte sur les bras partageant une baseline : E2 et E3 en
profitent, E1 non.

---

## 7 bis. Le plancher de bruit MESURÉ le 2026-09-21 — il n'est pas nul

E1 a été jouée sur le persona **861500 (Capucine Boulay)**, deux témoins sans choc, mêmes graines,
mêmes réglages, cache coupé, température 0.

| | Bras A (42 j) | Bras B (1 semaine simulée) |
|---|---|---|
| `experiments/archive/` | `2026-09-21_11_11` | `2026-09-21_14_28` |
| Décisions | 201 | 31 |

**Résultat : 1 écart de mode sur 31 décisions appariées, soit 3,2 %.**

| Le 21 mars à 19 h 03 | Marche | Transports collectifs | Mode tiré |
|---|---:|---:|---|
| Bras A | 0,15 | 0,85 | transports collectifs |
| Bras B | 0,30 | 0,70 | **marche** |

Le tirage est déterministe (graines identiques, cache coupé) : **c'est le modèle qui n'a pas rendu
deux fois la même distribution**, à température 0. Une décision dont deux options sont proches
bascule. À noter : la marche vaut 0,15 dans le bras A, **exactement** `seuil_troncature` — cette
décision était sur une frontière, comme le choc de 30 minutes l'est sur le seuil de gravité.

### Ce que cela change pour la rédaction

L'attendu du § 7 — « 0 écart de mode » — **n'est pas tenu**, et la campagne du ticket 077 qui
mesurait 0 sur 44 décisions doit se lire comme un tirage chanceux plutôt que comme une propriété.
Un effet de choc devra dépasser ce plancher pour être attribuable. Sur la campagne de septembre
l'effet allait de 95 % à 0 % de part voiture, très au-dessus — mais **le plancher se déclare, il
ne se tait pas.**

### Ce que la décision du 2026-09-22 y change

Ce plancher servait d'argument au **témoin interne** du ticket 059 § 6.4 : un foyer non exposé
dans le **même** run, parce que comparer deux runs distincts l'aurait fait entrer dans l'effet
mesuré. L'auteur a retiré cette exigence le 22 septembre — le chapitre 7 ne décrit plus les trois
rôles, et le 059 cesse de demander un foyer témoin.

**Le plancher, lui, ne change pas de valeur et ne cesse pas d'exister.** Ce qui change, c'est
d'où il vient : il n'est plus produit par le run de campagne, il se reprend d'ici (3,2 %, une
seule mesure, sur un seul persona) ou se réétablit par un rejeu à l'identique. Deux conséquences
à porter dans toute lecture de résultat :

- **La valeur est fragile.** Un écart sur trente et une décisions appariées, un persona, un
  modèle donné. Elle ne se transporte pas telle quelle à une autre population ni à un autre
  décideur — `scripts/analysis/presse/scoring.py` la demande en paramètre
  (`plancher_de_bruit`) précisément pour qu'elle soit **déclarée avec le résultat** et non
  supposée.
- **Un rejeu à l'identique reste le seul moyen de l'établir pour un décideur donné.** Il coûte
  un bras de plus, et c'est le prix du retrait du témoin interne : le témoin interne le donnait
  « sans rien payer de plus », il faut désormais le payer ou l'assumer repris d'ailleurs.

### DÉCISION DE L'AUTEUR, 2026-09-21

Plancher non nul **assumé et déclaré**, campagne poursuivie. La mesure sérieuse est **reportée**.

### À FAIRE PLUS TARD — chiffrer le plancher pour de bon

Deux témoins ne disent pas si 1/31 est le taux ou un accident. Il faut **trois ou quatre témoins
supplémentaires**, arrêtés à une semaine simulée (~30 min chacun), pour donner un taux avec son
intervalle. Trois questions à trancher à cette occasion :

1. le basculement vient-il des probabilités rendues, ou de `seuil_troncature = 0,15` qui élimine
   l'option d'un côté et pas de l'autre ? Le cas mesuré ne permet pas de les séparer ;
2. le plancher est-il le même selon les modes ? Les 16 décisions voiture sont identiques dans les
   deux bras ; les écarts se concentrent sur le couple marche / transports collectifs ;
3. faut-il un plancher par persona ? Celui-ci est mesuré sur 861500 seulement.

⚠ Ne pas toucher au tirage pour réduire le plancher : cela changerait le dispositif mesuré et
romprait la comparaison avec les campagnes antérieures.

---

## 8. Ordre d'exécution

1. **Lot B** — l'enquête, pour qu'elle tourne dès la prochaine campagne et que E2/E3 la portent d'office.
2. **Lot A** — la fenêtre dérivée, puis E2 en contrôle de non-régression, puis E3.
3. **Lot F, F4** — la conversion d'`experiments.yaml`, après le lot A qui fixe le paramètre cible.
   C'est le point que l'article cite, et il ne coûte rien.
4. **Lot E** — le modèle journalisé, gratuit, à faire au passage.
5. **Lot F, F1 puis F2 et F3** — la mesure se relève sur E2, la garantie EDF se vérifie ensuite,
   le rejeu des chiffres datés vient en dernier.
6. **Lot D** — les runs enfants, quand la facture de E3 le justifiera.
7. **Lot C**, piste locale comprise — le routage par catégorie en dernier : c'est celui qui
   oblige à refaire E1.

Chaque lot : contrat de tests d'abord dans `specs/ticket_095/tests.md`, puis code, puis documentation
et entrée de changelog, puis signalement d'impact article.

---

## 9. Références

- Carole Adam & Benoit Gaudou (2025), *A survey about perceptions of mobility, to inform an agent-based
  simulator of modal choice*, arXiv:2502.12058 — version longue anglaise du papier JFSMA 2024. Les six
  critères, l'échelle 0-10, les deux vecteurs (priorités et perceptions) et la formule de score.
- Carole Adam & Benoit Gaudou (2024), *An agent-based model of modal choice with perception biases and
  habits*, arXiv:2406.02063 — la fenêtre glissante sur les 100 derniers trajets et le filtre de
  perception qui dérive vers le mode habituel. Référence du chantier « empiler sans réviser », hors
  périmètre de ce ticket.
- Ticket 048 — le calendrier de consolidation et l'échelle d'oubli, **clos le 2026-09-21** :
  ses trois points de code sont en service, son reliquat est le lot F et la piste locale du lot C.
- Ticket 077 — la campagne qui a produit le constat.
- Ticket 085 — la restriction d'instances par run, que le lot C étend.
- Ticket 091 — l'identité de run, que les lots A, C et D alimentent.
- Ticket 093 — les mesures par jour, où les courbes de E2-E4 se liront.
- `docs/arch/memory-stm-ltm.md` — la liste complète des travaux dont l'architecture mémoire dérive.
