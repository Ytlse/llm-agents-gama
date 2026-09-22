# Ticket 059 — plan d'architecture des sept lots

> ⚠ **PÉRIMÉ SUR TROIS POINTS depuis le 2026-09-21/22.** Ce fichier a été écrit avant les
> arbitrages du quatrième tour (`questions.md`). Trois choses n'ont plus d'objet :
> **(1)** la condition **C3 paraphrase neutre** est retirée du protocole — le lot 1 n'écrit pas de
> `paraphrase.txt`, et `lexique_mobilite` ne sert plus qu'à vérifier le texte témoin ;
> **(2)** la condition **C5 référence tabulaire à événement encodé** est retirée — le point de
> comparaison est un décideur à règles rigides qui ne lit pas, rejoué hors ligne (Q20) ;
> **(3)** l'**étage 1** (3 299 déplacements, mémoire éteinte, hors simulateur) ne se joue plus —
> tout est longitudinal, quelques foyers sur plusieurs jours, mémoire allumée.
> L'ancienne C4, le texte témoin, prend le numéro **C3**. Les identifiants C1 à C9 de `tests.md`
> numérotent des **cas de test du corpus** et n'ont rien à voir avec les conditions du protocole.
> Ce fichier n'est pas réécrit tant que le lot 1 n'est pas repris : il est lu avec cet en-tête.

Écrit le 2026-09-21, après le GO de l'auteur sur les « sept lots codables aujourd'hui ».
**Aucune ligne de code n'est écrite avant validation de ce plan** (règle plan-first).

Le contrat de tests correspondant est dans [`tests.md`](tests.md), les questions ouvertes dans
[`questions.md`](questions.md). Quatre d'entre elles bloquent le lot 4.

---

## Ordre d'exécution proposé

```
  L2 grille ──► L1 corpus ──► L3 étage 1 ──────────────────────► un CHIFFRE pour le ch. 7
   (½ j)         (1 j)         (1-2 j, 800 requêtes)             sans aucun run GAMA

                     L6 population ──► L4 canal ──► L5 mesure ──► L7 figures
                       (½ j)            (2 j)        (1 j)          (1 j)
                                          │
                                          └─ bloqué par Q1, Q2, Q5, Q6
```

**L3 passe avant L4 délibérément.** Il produit le premier chiffre publiable du chapitre 7 pour
800 requêtes et sans simulateur, là où la chaîne L6→L4→L5 demande un run. Un chiffre tôt vaut
mieux qu'une mécanique complète sans chiffre.

**Aucun lot ne touche la mémoire.** Ni gravité, ni oubli, ni viviers, ni concepts, ni seuil. Le
seul lot qui entre dans le chemin de production est L4, derrière un drapeau éteint par défaut.

---

## Lot 2 — la grille des vingt signes, gelée

### Fichiers

| Fichier | Nature |
|---|---|
| `docs/paper/sources/actualites/grille_signes.yaml` | **neuf** — la grille gelée |
| `services/llm-agents/tests/test_059_grille.py` | **neuf** |

### Structure

```yaml
version: 1
gele_le: '2026-09-__'
source: RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md § 2 et § 3
articles:
  a09_vent_autan:
    titre: "Rafales à plus de 80 km/h, parcs fermés"
    cellules:
      voiture:  {signe: '+', intensite: 2, motif: "habitacle comme refuge au stress acoustique"}
      velo:     {signe: '-', intensite: 3, motif: "déséquilibre sur les ponts, parcs fermés"}
      marche:   {signe: '-', intensite: 3, motif: "poussière, chutes de branches"}
      tc:       {signe: '+', intensite: 2, motif: "métro abrité, franchissement sous-fluvial"}
```

### Logique

- **Vingt cellules, cinq articles par quatre modes.** Ni plus ni moins : un test le vérifie.
- `signe ∈ {+, -, 0}` et `intensite ∈ {0,1,2,3}`, avec l'équivalence stricte `signe == '0' ⟺
  intensite == 0`. Une cellule « pas d'effet attendu » est une **prédiction**, pas une abstention.
- Les **trois cellules ambiguës** du § 4.2 du ticket (marche sous La Machine, voiture sous la
  grève des éboueurs, marche sous VélôToulouse) prennent `signe: '0'` sous l'hypothèse Q4.
- `motif` est obligatoire et fait une ligne : une prédiction sans raison ne se discute pas.
- L'empreinte SHA-256 du fichier entre dans l'en-tête de tout rapport de dépouillement. **Une
  grille modifiée après une campagne se voit**, et c'est le seul point qui rend le
  « pré-enregistré » vérifiable.

---

## Lot 1 — le corpus textuel

### Fichiers

| Fichier | Nature |
|---|---|
| `docs/paper/sources/actualites/articles_txt/<id>/brut.txt` · `paraphrase.txt` · `temoin.txt` | **neufs**, 5 × 3 |
| `docs/paper/sources/actualites/articles_txt/MANIFEST.yaml` | **neuf** |
| `scripts/data/presse/extraire_textes.py` | **neuf** — HTML archivé → texte |
| `scripts/data/presse/lexique_mobilite.py` | **neuf** — la liste interdite en C3 et C4 |
| `services/llm-agents/tests/test_059_corpus_presse.py` | **neuf** |

### Structure du manifeste

```yaml
articles:
  a09_vent_autan:
    source: {fichier: articles_html/09_vent_autan_fermeture_parcs.html, sha256: …, url: …}
    brut:       {sha256: …, mots: 312, langue: en}
    paraphrase: {sha256: …, mots: 298, langue: en}
    temoin:     {sha256: …, mots: 305, langue: en, article_source: 21_ombrieres_rue_alsace.html}
    ecart_longueur_temoin: 0.023
```

### Logique, et les quatre règles que le test fait respecter

1. **C2 est cité, jamais réécrit.** Le texte brut est l'extrait de l'article archivé ; son
   empreinte et celle du HTML source sont au manifeste. Ce que le canal du lot 4 injecte est
   comparé à cette empreinte à chaque run.
2. **C3 ne contient aucun mot de mobilité.** La liste vit dans un fichier, pas dans le test :
   *metro, subway, bus, tram, train, bike, bicycle, cycling, car, driving, walk, pedestrian,
   pavement, sidewalk, road, street, lane, station, platform, parking, traffic, commute…* Une
   paraphrase qui en contient un est **refusée**, pas signalée.
3. **C4 obéit à la même interdiction** et s'apparie en longueur à ±15 % de son article. Un témoin
   qui parlerait de circulation ne serait pas un témoin.
4. **Tous les textes sont en anglais.** Le dispositif entier l'est depuis le ticket 074 ; une
   phrase française dans un prompt anglais réintroduit exactement le facteur que la bascule a
   supprimé, et que le ticket 072 mesure séparément.

### La traduction — TRANCHÉ par l'auteur le 2026-09-21

Les cinq articles sont des textes de presse **français**, et le dispositif est anglais depuis le
ticket 074. **Décision : on traduit, avec mention explicite.**

- Chaque article porte **deux fichiers** : `brut.fr.txt`, l'extrait de la source archivée, et
  `brut.txt`, sa traduction anglaise. Les deux ont leur empreinte au manifeste. Idem pour les
  paraphrases et les témoins, soit **30 fichiers** et non 15.
- Le texte injecté dans le prompt porte la mention **« Translated from French »**, à l'intérieur de
  l'entrée, visible du modèle. Ce n'est pas un commentaire de dépôt : c'est une information que
  l'agent a, et le dispositif n'a pas à la lui cacher.
- La traduction est faite **une fois**, avant toute campagne, et n'est plus jamais retouchée. La
  garde de citation s'applique désormais aux deux versions : l'empreinte française prouve la
  fidélité à la source, l'empreinte anglaise prouve qu'aucune campagne n'a joué sur un texte
  différent d'une autre.
- `MANIFEST.yaml` porte `traduction: {par: <humain | modèle et sa version>, le: <date>}`. Une
  traduction anonyme ne se vérifie pas.

⚠ **L'article doit dire que les textes sont traduits.** C'est un choix de protocole, pas un détail
de mise en œuvre : un relecteur qui lit « articles réels de la presse locale toulousaine » et
trouve de l'anglais dans le dépôt a le droit de demander pourquoi.

---

## Lot 3 — l'étage 1 (c'est le ticket 064)

### Fichiers

| Fichier | Nature |
|---|---|
| `scripts/analysis/eval_presse_locale.py` | **neuf** |
| `services/llm-agents/tests/test_059_eval_presse.py` | **neuf** |

### Trois sous-commandes, et elles se lancent séparément

```bash
# 1. tirer et GELER l'échantillon — aucun appel au modèle
python -m scripts.analysis.eval_presse_locale echantillon --n 200 --graine 59 \
       --run <run de référence> -o docs/traces/<date>_presse/echantillon.json

# 2. jouer les conditions — un appel par déplacement et par condition
python -m scripts.analysis.eval_presse_locale jouer --echantillon … \
       --article a13_punaises --conditions C1,C2

# 3. dépouiller — aucun appel
python -m scripts.analysis.eval_presse_locale scorer --resultats … --grille …
```

### Structures

- `echantillon.json` : liste de déplacements `{move_id, person_id, activity_id, mode_reference,
  motif, tranche_horaire, zone}` plus les strates, la graine et l'empreinte du run source.
- `resultats_presse.csv` : `move_id, article, condition, mode_choisi, p_voiture, p_velo, p_marche,
  p_tc, provider, model, option_order_seed`.
- `scoring_presse.md` : par article et par mode, l'écart C2−C1 apparié avec son intervalle
  (bootstrap par **personne**), le signe observé, le signe attendu, puis $S_{\text{sign}}$, le
  binomial, le $\kappa$ pondéré, et les deux contrôles — C4−C1 et le rejeu à l'identique.

### Les quatre gardes

1. **Les mêmes déplacements pour toutes les conditions.** L'appariement fait la puissance ; un
   échantillon retiré par condition la détruit.
2. **`option_order_seed` retiré au hasard à chaque requête**, contrôle rendu nécessaire par la
   sensibilité à l'ordre que mesure SILICA.
3. **Le rejeu à l'identique de C1** est une condition à part entière, pas une option : sans lui,
   « C4 déplace moins que C2 » se compare à zéro au lieu de se comparer au bruit.
4. **Les empreintes du corpus et de la grille sont dans l'en-tête du rapport.** Un score sans elles
   ne prouve pas que la prédiction précédait la mesure.

### Garde de vacuité

Un mode absent de l'échantillon sort **« non concluant »**, jamais 0,0. Dans ce dépôt, l'absence
de mesure produit le score parfait, et ce motif a déjà menti.

---

## Lot 6 — la population de foyers

### Fichiers

| Fichier | Nature |
|---|---|
| `scripts/data/population/extraire_foyers.py` | **neuf** — distinct d'`extraire_sous_population.py`, qui prend des individus par prédicat |
| `data/population/population_20_foyers_059/population.json` · `MANIFEST.yaml` | **neufs** |
| `services/llm-agents/tests/test_059_population_foyers.py` | **neuf** |

### Logique

- L'unité d'extraction est le **foyer entier**, jamais l'individu : extraire un membre sans l'autre
  supprime l'objet même de l'étage 3.
- Critères de P0 et P1, déclarés et journalisés : `household.id` partagé, **taille 2**, les deux
  membres mobiles, au moins un abonné TC (pour l'article « punaises »), et un groupe témoin tiré
  sur les mêmes critères.
- **Déterministe.** Ordre des identifiants numériques, comme `extraire_sous_population.py` ; la
  graine du tirage témoin/exposé est au manifeste.
- Le `MANIFEST.yaml` reprend la forme du 093 et porte **en tête** la même mention : *ce n'est pas
  un sceau, vingt agents ne mesurent aucune part modale*.

---

## Lot 4 — le canal `information`

**Les quatre questions bloquantes sont tranchées (2026-09-21).** Q1 : l'agent juge lui-même
l'importance de ce qu'il lit, il n'y a plus de constante. Q2 : un seul lecteur par foyer. Q5 : le
jour de parution est tiré au sort. Q6 : chaînage des véhicules actif partout.

⚠ **Q1 change le lot en profondeur, et en bien.** `gravite: 0.70` disparaît de la déclaration ; à
la place, un appel de jugement rend l'un des cinq échelons de `llm/gravite.py`, et
`gravite_concept(i_llm, 0.0)` fait le reste — un article ne portant aucun fait mesuré, le jugement
décide seul, par la règle déjà en vigueur. Deux points restent ouverts, au § 13 du ticket :
**quand** le jugement est demandé (Q16, proposition : à la lecture) et **que faire d'un échelon
hors grille** (Q17, proposition : refus et alarme, jamais de repli silencieux).

### Fichiers

| Fichier | Nature |
|---|---|
| `services/llm-agents/llm/informations.py` | **neuf**, frère de `llm/chocs.py` |
| `services/llm-agents/settings.py` | `InformationsConfig{enabled, fichier}` — **pas de réglage de gravité**, l'agent juge |
| `services/llm-agents/urban_mobility_agents/simulation_controller.py` | un appel à la bascule de journée |
| `services/llm-agents/experiences/experience.py` | lever le refus E6 pour le **seul** `type: information` |
| `services/llm-agents/config/presse/*.yaml` + `README.md` | **neufs**, un fichier par article |
| `Makefile` + `infra/docker-compose.yml` | levier `PRESSE=` et passe-plat, sur le modèle de `CHOC=` |
| `services/llm-agents/tests/test_059_informations.py` | **neuf** |

### Format de déclaration

```yaml
information: a13_punaises_metro
libelle: "Bed bug scare on the metro"
source: "presse locale — punaise-de-lit-info.fr, archivé sous articles_html/13_…"
texte_fichier: docs/paper/sources/actualites/articles_txt/a13_punaises/brut.txt
texte_sha256: "…"          # vérifié au chargement contre le fichier

# Le jour de parution est TIRÉ AU SORT dans cette fenêtre, par foyer, à graine fixe : deux foyers
# ne lisent pas le même jour, et un effet de calendrier ne peut plus se confondre avec celui de
# l'article.
parution:
  fenetre_jours: [9, 13]
  graine: 59

# Pas de `gravite` : l'AGENT juge ce qu'il vient de lire, sur les cinq échelons de llm/gravite.py.

exposition:
  regle: foyers             # foyers | agents | tirage
  foyers: ["5177", "18056"]
  lecteurs_par_foyer: 1
  graine: 59
```

### Structures (dataclasses gelées, comme `chocs.py`)

| Classe | Porte |
|---|---|
| `Information` | `information_id, libelle, source, texte, empreinte_texte, fenetre_parution, graine, exposition` — **plus de `gravite`** |
| `Exposition` | `regle, foyers, agents, part, graine, lecteurs_par_foyer` |
| `RegistreInformations` | le texte en vigueur, les lecteurs tirés, les compteurs, le journal |
| `CompteursJournee` | lecteurs servis, foyers touchés, refus par règle |

### Logique du registre

| Méthode | Ce qu'elle fait |
|---|---|
| `jour_du_run(ts)` | **réutilise `jours_ecoules` du ticket 075**, comme `chocs.py` — jamais le premier timestamp observé, sans quoi une reprise à chaud décalerait la parution |
| `lecteurs(population)` | tire **un** membre mobile par foyer exposé, par hachage déterministe `graine:information_id:household_id`, et **journalise le tirage** |
| `jour_de_parution(household_id)` | tire le jour dans la fenêtre déclarée, par hachage stable `graine:information_id:household_id` |
| `due(ts, household_id)` | vrai le jour de parution DE CE FOYER, une seule fois, avant tout réveil |
| `juger(lecteur, texte)` | demande l'échelon au modèle, rend `gravite_concept(gravite_jugee(niveau), 0.0)` ; un échelon hors grille est REFUSÉ avec `[ALARME]`, jamais remplacé en silence |
| `entree_pour(person_id)` | le texte, préfixé `[ PRESSE ] This morning I read in the paper: « … »` |
| `tracer(...)` | une ligne par lecteur servi dans `informations.jsonl` |

### Le point d'injection

À la **bascule de journée** du contrôleur, dans le même bloc que le déclenchement de l'enquête
(`simulation_controller.py` ≈ l. 1775), **avant** tout réveil d'agent. L'entrée part en mémoire
courte avec l'importance que **le lecteur lui-même** a attribuée, et c'est tout : la force
`min(2,8 × (1 + 6·g), 30)` et le service dans le bloc « Ce qui a changé récemment » suivent sans
une ligne de plus.

⚠ **Ce n'est pas le point d'injection des chocs**, et la différence est le cœur du régime : un choc
s'applique à l'arrivée, après la décision ; un article est su **avant** de décider.

### Les cinq refus au chargement

| Refus | Pourquoi |
|---|---|
| empreinte du texte ≠ manifeste du lot 1 | le texte est **cité**, jamais réécrit — la garde propre à ce canal |
| consigne (« avoid », « you should ») | reprise mot pour mot des marqueurs de `chocs.py` |
| verdict sur un mode (« this line is unreliable ») | la croyance est ce que la réflexion doit produire |
| intention (« from now on I will… ») | idem |
| fenêtre de parution hors run, règle d'exposition inconnue, foyer absent de la population | une faute de frappe qui ne touche personne produirait un run entier sans symptôme |
| un champ `gravite` dans la déclaration | l'agent juge ; une gravité posée à la main rétablirait le paramètre que Q1 a supprimé |

Plus l'alarme de `chocs.py`, reprise telle quelle : **`[ALARME]` si le cache de décisions est
actif** — sa clé ne porte ni l'article ni le souvenir.

---

## Lot 5 — la mesure

### Fichiers

| Fichier | Nature |
|---|---|
| `scripts/analysis/mesures/calcul.py` | fonction `presse_par_jour(...)` |
| `scripts/analysis/mesures/ecriture.py` | écriture de `presse_par_jour.csv` |
| `scripts/analysis/mesures/prometheus.py` | trois séries : part du mode visé par rôle, énoncés transmis, souvenir servi |
| `services/llm-agents/tests/test_059_mesures_presse.py` | **neuf** |

### Entrées, et rien d'autre

`informations.jsonl` (qui a lu, quand) · `moves.csv` (les décisions) · `agent_memory_events.jsonl`
(les concepts et leurs opérations) · le point de reprise du jour (l'état).

### Les quatre règles du 093 s'appliquent sans exception

Journée à 3 h · « la veille » est le jour **vécu** précédent · **une cellule vide n'est pas un
zéro** · les jours relatifs se redérivent des horodatages du journal, jamais d'une colonne écrite
pendant le run.

### Le garde-fou du confondant

La colonne `contrainte_chaine` est obligatoire. **Un changement de mode concomitant à une
contrainte de chaîne ne compte pas comme diffusion** — sans quoi le lecteur qui libère la voiture
du foyer se lirait comme une information transmise.

---

## Lot 7 — les figures

### Fichiers

`scripts/analysis/figure_presse.py` (**neuf**, F1 · F2 · F3), sur le modèle de
`figure_fenetre_choc.py`, versionné par `figures_versionnees.py`.

### Logique

- Écrites **avant** le premier run, sur des données de forme. Une figure dont le script n'existe
  qu'après la mesure se taille sur ce qu'elle a trouvé.
- **En anglais, légende comprise.**
- Chacune sort « non concluant » plutôt qu'une courbe vide quand l'effectif minimal déclaré n'est
  pas atteint.

---

## Ce que ce plan ne fait pas

- Il ne lance **aucun run**. P0 vient après L4 et L5, et il demande son propre feu vert.
- Il ne touche **aucune règle de mémoire**.
- Il n'écrit **rien** dans `docs/paper/article/`.
- Il ne traite pas l'étage 3 : le canal du foyer est le ticket 078, qui n'a aucun code. Les lots
  ci-dessus le préparent — la population de foyers, la colonne de rôle, la figure F2 — sans le
  faire à sa place.
