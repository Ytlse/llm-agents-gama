# Ticket 045 — Un seul substrat : archiver ce qui n'est plus la v5, et reconstruire les expériences

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-11 à la demande de l'auteur, rien n'est lancé.
>
> Prérequis : aucun. Ce ticket **bloque** toute mesure destinée à l'article — les 36 exécutions
> existantes sont à refaire, et les relancer avant la décision du lot 2 les ferait refaire deux fois.

## Décisions de l'auteur, 11 septembre 2026

| Point | Décision |
|---|---|
| **A1 — la journée doit-elle se refermer ?** | **Oui.** Le retour au domicile est un déplacement et doit être décidé. `jeu.py` se corrige **avant** la reconstruction : sans cela, les bras LLM seraient repayés sur une journée encore amputée. Conséquence chiffrée : 3 299 déplacements attendus sur la v5 au lieu de 2 405, soit **+37 % d'appels par bras**. |
| **Plancher « plus court chemin »** | Sans objet : l'auteur visait **le plus rapide**, qui est le décideur `duree_minimale` déjà implémenté. Aucun décideur à ajouter. |
| **`gemini-3.1-flash-lite-preview`** | Écarté. On ne garde que le modèle stable `gemini-3.1-flash-lite`. Le lot 4c passe de sept à **six** bras. |
| **Plusieurs graines par bras LLM** | Plus tard. Une seule passe par bras dans ce ticket ; la variabilité inter-graines fera l'objet d'un ticket distinct. |
| **Garde-fou des populations archivées** | Retenu sous la forme proposée : refus dans le code, contournable seulement par un champ explicite `population.archivee_confirmee: <motif>` dans la définition. |
| **Lot 4d (prompts experts)** | Les variantes `expert_chaine` et ses `m*` **restent en place** dans `prompts.yaml`, mais **aucune expérience n'est planifiée** pour elles dans ce ticket. Conséquence assumée : pas de palier « prompt calibré » mesuré sur la v5 tant qu'un ticket ultérieur ne les planifie pas. |

## Le constat

Les 36 exécutions de la plateforme d'expériences ont toutes lu la **cohorte v1**
(`data/population/population_1000_AAMAS/population.json`, `f67b0777…`, scellée le 2 septembre),
alors que la cohorte de référence de l'article est la **v5** (`de73532e…`, scellée le 4 septembre).
Aucune mesure n'existe sur la v5.

La trace est fiable des deux côtés : `experiences/population.py` vérifie l'empreinte annoncée par
le `MANIFEST` au chargement et refuse une population altérée, puis écrit les deux empreintes dans
`synthese.json`. Recoupement indépendant : chaque synthèse annonce `attendus_bruts: 2693`, qui est
le compte de la v1 ; la v5 en donnerait 2 405 sous la même convention.

| Objet | État |
|---|---|
| 46 définitions `data/experiences/*/experience.yaml` | **toutes** sur la v1, sous trois orthographes du même chemin |
| 34 exécutions abouties (7 → 11 septembre) | **toutes** sur la v1 |
| 1 exécution arrêtée, 1 close en cours de journée (`exp_rf`) | v1 |
| `data/jeux/population_1000_AAMAS_20260316` (seul jeu existant) | scellé contre la v1 |
| Runs de simulation depuis le 4 septembre 15:51 | v5 — mais **deux seulement** ont produit un `moves.csv`, le 4 septembre |
| Run épinglé par la page de synthèse (`2026-08-27_17_57`) | antérieur à tout scellement |

**Cause racine, deux mécanismes qui se renforcent.** Le formulaire du tableau de bord propose
`populations()[0]`, et `populations()` trie les dossiers scellés par ordre alphabétique :
`population_1000_AAMAS` précède `_v3`, `_v4`, `_v5` — la v1 est donc le **défaut**. Et
`DEFAUTS_NOMMAGE["population"] = "population_1000_AAMAS"` (`experiences/nommage.py:73`) rend cette
population **muette dans le nom** de l'expérience (règle N7) : aucun des 46 noms ne mentionne de
population, ce qui se lisait comme « rien à signaler » et signifiait « toutes sur la v1 ».

## Six alertes trouvées en chemin, et l'une est plus grave que la population

**A1 — la journée n'est pas refermée : le retour au domicile n'est jamais une décision.**
`experiences/jeu.py:115` (`deplacements_attendus`) énumère les **paires consécutives** d'activités.
Or la chaîne d'activités est **cyclique** — la première activité `home` commence la veille au soir,
et la dernière activité de la journée est suivie d'un retour au domicile. Le contrôleur de
simulation, lui, referme le cycle : `(curr_idx + 1) % len(activities)`
(`simulation_controller.py:806, 860, 1750`) et solde la boucle au retour au domicile (`:1811`).

Conséquence : la plateforme mesure **n − 1** déplacements par personne là où la simulation en joue
**n**. Sur la v1, 2 693 décisions au lieu de 3 693 — **27 % de la journée jamais décidée**. Et
l'omission n'est pas aléatoire : elle retire exactement le **dernier trajet de la journée**, celui
où la règle de cohérence des véhicules contraint le plus le choix (un agent parti en voiture rentre
en voiture). Les parts modales mesurées par la plateforme sont donc celles d'une journée amputée de
son retour, ce qui pousse structurellement vers les modes d'aller.

Le docstring de `experiences/population.py` annonce l'inverse — « le nombre de déplacements
attendus dérivable à l'identique des deux côtés (J2, E22) ». La garantie porte sur le chargeur et
les horaires ; l'énumération, elle, diverge.

**A2 — deux empreintes sous un même nom de variante. TRANCHÉ le 2026-09-11 : illusion, et corrigé.**
`prompt_minimal` a été servi sous deux empreintes (`88f0aefcff` pour les deux bras Antigravity,
`9afe7d4a52` pour les neuf autres) ; `minimal_persona` de même. **Le texte servi était pourtant le
même.** L'écart venait d'une résolution de chemin : `empreinte_gabarit` cherchait le gabarit
d'option `travel_plan_describe_v2.j2` sous la racine du dépôt, or le conteneur `controller` monte
`llm-agents` sur `/app` — le fichier y est en `/app/text_helper/…` et était cherché en
`/llm-agents/text_helper/…`. Introuvable, il sortait du hachage **sans bruit** : l'hôte hachait
deux morceaux, le conteneur un seul. La comparabilité des deux lots n'est donc pas en cause.

Corrigé : le gabarit se résout par rapport au dossier `llm-agents`, présent des deux côtés, et un
morceau introuvable lève une ALARME au lieu de disparaître. Vérifié des deux côtés : `88f0aefcff`.

**A3 — le dénominateur bouge. REQUALIFIÉ le 2026-09-11, et corrigé.** Recompté : les **23 exécutions
complètes ont toutes 48** inexploitables, qui est le compte `sans_proposition` du manifeste du jeu ;
les valeurs 44, 1 et 0 ne viennent que d'exécutions avortées. Aucune comparaison entre exécutions
complètes n'était faussée. Le défaut réel est ailleurs et reste vrai : le compteur **s'accumulait
au fil des décisions** au lieu d'être dérivé du jeu à l'ouverture, si bien qu'une exécution
interrompue n'annonçait pas le même dénominateur qu'une exécution complète.

Corrigé : `Jeu.inexploitables(attendus)` dérive l'ensemble du jeu à l'ouverture, et tout écart
constaté à la clôture lève une ALARME.

**A4 — aucune exécution ne porte l'état du dépôt.** `empreintes.depot = {commit: null,
arbre_propre: null}` dans les 36 exécutions, et `dependances.commit`/`osmnx_graph_key` sont `null`
dans le manifeste du jeu. Aucune mesure existante ne peut être rattachée à un état du code.

**A5 — les choix forcés entrent dans les parts, et leur nombre dépend du bras.**

En clair, avec un exemple. Jean part travailler en voiture le matin. Le soir, sa voiture est au
bureau : le seul itinéraire qui existe pour rentrer est la voiture. **Personne ne décide rien** —
ni le modèle de langue, ni l'oracle, ni le tirage au sort : il n'y a qu'une option. Ce trajet est
pourtant compté dans les parts modales publiées, comme s'il avait été choisi.

Or le nombre de ces trajets sans choix **dépend du bras**, puisqu'il découle de ce que le bras a
décidé plus tôt dans la journée : prendre la voiture le matin, c'est s'imposer un retour en voiture
le soir. Mesuré sur les 23 exécutions complètes, à population et jeu identiques :

| Bras | Décisions à itinéraire unique |
|---|---:|
| `duree_minimale` (le plus rapide) | 393 |
| `majoritaire_voiture` | 381 |
| bras LLM | 300 à 359 |
| `aleatoire` | 286 |

Deux conséquences. **Les bras se ressemblent plus qu'ils ne le sont** : 11 à 15 % de leur journée
est identique et non décidée, ce qui comprime mécaniquement les écarts qu'on cherche à mesurer. Et
**un bras est partiellement noté sur les conséquences de ses propres choix du matin**, non sur ses
décisions.

**Arbitrage de l'auteur, 11 septembre : la contrainte n'est pas le défaut, elle est le cadre.** Un
trajet imposé par un choix antérieur reste un fait de la journée simulée, et une vraie journée en
comporte. Ce ticket ne cherche donc pas à neutraliser la chaîne. Il en tire deux exigences :

1. **Rapporter le compte des choix forcés par bras** à côté de ses parts modales, et publier les
   parts **des deux façons** — toutes décisions, et hors itinéraire unique. Non pour corriger un
   biais, mais parce qu'un seul chiffre mélange ce que le décideur a décidé et ce que la situation
   lui imposait, et que la seconde quantité varie d'un bras à l'autre.
2. **Traiter l'asymétrie d'anticipation**, qui est la vraie question que la chaîne soulève — objet
   de l'alerte A6.

### A6 — l'agent anticipe la journée, le modèle tabulaire ne le peut pas, et le contrat dit le contraire

L'agent reçoit, à chaque décision, l'**agenda des trajets restants** avant le retour au domicile et
la **météo des tranches horaires restantes** — champs `agenda` et `day_outlook` de la charge utile,
ajoutés par le ticket 014 sous l'intitulé explicite « anticipation de la chaîne de la journée »
(`mobility_llm/persona.py`). Il peut donc décider le matin en sachant ce que ce choix lui imposera
le soir. Le modèle tabulaire, lui, reçoit 21 variables qui ne portent **rien** sur la suite de la
journée : personne, ménage, motif, heure de départ, géométrie du trajet courant. Il décide chaque
déplacement isolément.

Trois conséquences, dans l'ordre de gravité.

**a) Le contrat d'évaluation, tel qu'il est écrit, est faux.** La règle 1 de la section 1.3 dit que
l'agent et les modèles tabulaires « reçoivent les mêmes 21 variables d'entrée ». L'agent en reçoit
davantage : l'agenda, la météo à venir, et sa mémoire. La formulation doit dire ce qui est vrai —
*les mêmes 21 variables décrivant la personne et le déplacement courant ; l'agent reçoit en outre
l'agenda de sa journée, la météo des tranches restantes et sa mémoire, et ce surplus est
précisément ce que la comparaison met à l'épreuve.* Ainsi énoncée, l'asymétrie cesse d'être une
faille du contrat pour devenir l'objet de l'étude.

**b) Le modèle tabulaire est jugé, en chaîne, sur une tâche qu'il n'a pas apprise.** Pire : il subit
les conséquences de ses propres choix du matin sans avoir pu les anticiper. Et l'effet moyen du
chaînage est **déjà dans ses probabilités**, puisqu'il a été ajusté sur des journées réelles, elles
aussi chaînées ; le simuler en chaîne applique la contrainte une seconde fois. Sa lecture en chaîne
est donc pessimiste, et il faut le déclarer.

**c) Le remède n'est pas de retirer la chaîne aux modèles tabulaires**, ce qui les créditerait d'une
voiture restée au bureau, produirait des journées physiquement impossibles et romprait la règle 3
(renormalisation sur l'offre) comme le principe du substrat unique. Le remède est **deux lectures
déclarées**, sur le patron que le dépôt emploie déjà partout (masse / mode élu, avant / après
renormalisation) :

| Lecture | Ce qu'elle mesure | À quoi elle se compare |
|---|---|---|
| **en chaîne** | le modèle comme moteur de décision dans la simulation, mêmes jeux de choix que l'agent | au bras LLM, terme à terme |
| **hors chaîne** | chaque déplacement isolément, offre restreinte par ce qui ne dépend pas des décisions antérieures (équipement du ménage, permis, faisabilité physique) | à l'enquête — c'est la tâche pour laquelle le modèle a été ajusté |

**L'écart entre les deux lectures est lui-même une mesure** : il chiffre ce que coûte de ne pas
anticiper la journée. C'est un résultat publiable, et c'est l'argument le plus direct en faveur des
agents génératifs que ce dispositif puisse produire — bien plus qu'une part modale mieux calée.
À produire pour les quatre familles de référence, dans le lot 4b.

## Ce qu'il faut faire

### Lot 1 — un seul substrat : archiver ce qui n'est plus la v5

- Déplacer les cohortes qui ne sont plus la référence dans `data/population/archive/` :
  `population_1000_AAMAS` (v1), `population_1000_AAMAS_v3`, `population_1000_AAMAS_v4`, et les
  fichiers nus de travail de `data/population/` qui ne servent plus. La v5 reste seule en place.
  Les dossiers scellés ne se modifient pas (règle du `MANIFEST`) : on les **déplace**, sans toucher
  à leur contenu, et le chemin d'origine est journalisé.
- Écrire `data/population/archive/README.md` : ce que chaque cohorte était, pourquoi elle est
  archivée, et la **règle** — *une population archivée ne se lit pas ; toute exception demande une
  confirmation explicite de l'auteur, consignée dans le ticket qui la demande.*
- Poser le **garde-fou dans le code**, pas seulement dans la prose : `resoudre_population()` refuse
  un chemin situé sous `data/population/archive/` — refus bruyant, code de sortie non nul, message
  nommant la v5 — sauf si la définition porte explicitement `population.archivee_confirmee: <motif>`.
  Un garde-fou qui n'existe que dans un README ne se déclenche jamais.
- `populations()` du tableau de bord n'expose plus les archivées, et son défaut devient la **dernière
  cohorte scellée par date de sceau**, jamais la première par ordre alphabétique.

### Lot 2 — le balayage : qu'est-ce qui pourrait encore invalider une mesure ?

Le lot 1 ferme une cause. Le balayage cherche les autres, **avant** de repayer 20 bras LLM. Les
quatre alertes ci-dessus en font partie ; A1 est bloquante et se tranche la première. À vérifier,
chacun par une mesure et non par lecture :

1. **A1, la journée refermée.** Comparer, sur un même run de simulation v5, le nombre de décisions
   par personne dans `moves.csv` au nombre d'activités de sa chaîne. Puis trancher : la plateforme
   referme le cycle comme la simulation, ou la définition de la journée change dans les deux. Aucun
   chiffre de l'article ne se publie avant.
2. **A2, l'empreinte de gabarit.** Dire ce que couvre `gabarit.sha256` et vérifier que deux bras du
   même nom de variante ont reçu le même texte.
3. **A3, le dénominateur.** Rendre l'ensemble des déplacements exploitables déterministe pour un
   couple (population, jeu) donné, ou dire ce qui le fait bouger.
4. **A4, l'état du dépôt.** Renseigner `commit` et `arbre_propre` à l'exécution, et la clé du graphe
   OSMnx dans le manifeste du jeu. Une mesure sans état de code n'est pas rejouable.
5. **Le gabarit des décideurs-modèles.** `exp_klr`, `exp_mnl`, `exp_rf` portent
   `gabarit.invalide: true` (règle M1) alors qu'un décideur de type `modele` n'envoie aucun prompt.
   Dire si le drapeau est du bruit — et alors ne pas l'écrire — ou s'il refuse la mesure.
6. **Les bras servis sous un prompt invalidé.** Quatre mesures complètes utilisent
   `minimal_persona`, invalidé le 10 septembre (M1, M3 — « pourquoi la marche n'obtient pas la plus
   forte probabilité » est un a priori modal). Elles sont invalides pour une raison **indépendante**
   de la population : à ne pas reconstruire sous ce gabarit.
7. **La fenêtre météo et le calendrier.** Le jeu est daté du 2026-03-16, politique `aleatoire`,
   graine 42 : vérifier que la date reste dans la fenêtre du protocole et que le jour tiré n'est pas
   un jour atypique du réseau.
8. **A5, les jeux de choix réalisés.** Publier les parts des deux façons et le compte des choix
   forcés par bras ; dire si le périmètre de comparaison inter-bras doit être restreint aux
   situations que tous ont réellement décidées.

**Cette liste n'est pas le balayage : elle en est le point de départ.** Consigne explicite de
l'auteur, 11 septembre : *aller chercher d'autres points*. Cinq alertes ont été trouvées en une
heure d'audit sur une question qui n'en cherchait qu'une ; rien ne dit qu'il n'en reste pas. Le lot
n'est pas clos quand les huit points ci-dessus sont traités — il est clos quand une recherche
délibérée n'en trouve plus, et le compte rendu dit **où** elle a cherché.

La méthode qui a produit les cinq premières, à reprendre :

- **comparer deux chemins qui devraient dire la même chose.** A1 est née de la comparaison entre
  l'énumération de la plateforme et celle du contrôleur de simulation. Partout où deux
  implémentations couvrent le même concept — parts modales, catégories de modes, temps terminaux,
  périmètre des couronnes, exploitabilité d'un déplacement —, les faire produire le même nombre sur
  le même substrat et exiger l'égalité.
- **relire les empreintes plutôt que les intentions.** Le substrat, le gabarit, le décideur et son
  artefact portent tous un sha256 dans `synthese.json`. Un audit se fait sur ces champs : une
  définition dit ce qu'elle voulait, une empreinte dit ce qui a été servi.
- **traquer le motif « l'absence de mesure produit le score parfait »**, récurrent dans ce dépôt :
  une offre à mode unique, une strate vide, une marge non mesurable, un repli compté comme une
  décision. Chercher systématiquement ce qui, faute de mesure, est compté comme un accord.
- **faire varier ce qui devrait être invariant.** Deux exécutions du même bras, deux bras sur le
  même substrat, deux régénérations d'une page : tout ce qui bouge sans raison déclarée est un
  défaut. C'est ainsi que le dénominateur mobile (A3) et les offres divergentes (A5) sont apparus.

Ce qui a déjà été vérifié **sain** au 11 septembre, à ne pas refaire :

| Vérifié | Résultat |
|---|---|
| Ordre des options présenté au modèle | randomisé par décision (`decision.py:255`, graine dérivée de la personne et de l'activité) — le contrôle annoncé par l'article est bien appliqué |
| Plafond à six options | trié canoniquement par durée puis code avant de plafonner, via le `_select_candidates` **partagé** avec la simulation |
| Décideurs-modèles | la masse est bien restreinte à l'offre puis renormalisée (`decideur_modele.py`), et les cas non imputables sont comptés et non réparés |
| Météo | tirée par personne depuis un CSV réel, bornes de dates vérifiées à la préparation |
| Sceau de population | vérifié au chargement, une population altérée est refusée |
| Règles de chaîne des véhicules en mode sans simulateur | appliquées : sur une exécution de référence, `vehicule_ailleurs` écarte 812 options et `retour_force` 823 — le mode sans simulateur n'est pas un classifieur hors sol |
| Chargeur de population | le **même** que la simulation (`EqasimJSONPopulationLoader`), donc mêmes personnes et mêmes heures programmées des deux côtés — c'est l'**énumération** qui diverge (A1), pas le chargement |
| Runs de simulation sans `static_config` (39) | aucun ne porte de `moves.csv` : démarrages avortés, aucune mesure en jeu |
| Décision de l'agent | tirage dans la masse de probabilité, graine dérivée de la personne et de l'activité (`decision.py:514`) — reproductible, et ce n'est pas un argmax |

### Lot 3 — archiver les expériences et repartir de zéro

- `data/experiences/` entier part dans `data/experiences/archive_v1_2026-09-11/` — définitions,
  exécutions, statuts. Rien n'est supprimé : ces mesures gardent leur valeur d'historique, et ce
  sont elles qui disent quoi reconstruire.
- Un `README.md` dans ce dossier : *mesures faites sur la cohorte v1, invalides pour l'article,
  conservées comme trace ; ne pas les rejouer, ne pas les citer.*
- Le jeu `population_1000_AAMAS_20260316` suit le même chemin (`data/jeux/archive/`).
- Base vierge : `data/experiences/` vide, `data/jeux/` avec le seul jeu v5 à construire.

### Lot 4 — reconstruire les définitions à lancer sur la v5

Préalable **gratuit** (hors ligne, aucun appel LLM) : construire le jeu
`population_1000_AAMAS_v5_20260316` — mêmes jour simulé, politique et graine que l'existant, pour
que seule la cohorte change.

Puis les définitions ci-dessous, **toutes** sur `data/population/population_1000_AAMAS_v5`, jeu
`population_1000_AAMAS_v5_20260316`, `mode: sans_simulateur`, horizon 1 jour, sans mémoire, sans
événement, graines 42, `max_candidats: 6`, tolérances horaires de référence. Ne sont reconstruits
que les bras dont la mesure v1 était **complète** (couverture ≥ 0,99) ; les bras tombés par quota,
jeton ou boucle de refus ne le sont pas.

**Lot 4a — planchers et heuristiques physiques (3 bras, gratuits)**

| Expérience | Décideur |
|---|---|
| `exp_alea_nosim` | `aleatoire`, graine 42 |
| `exp_durmin_nosim` | `duree_minimale` (le plus rapide de l'offre) |
| `exp_majvoiture_nosim` | `majoritaire_voiture` |

**Lot 4b — oracles et candidats oracle (4 bras, gratuits)**

| Expérience | Artefact |
|---|---|
| `exp_lgbm_jtir_nosim` | `scripts/progedo_logit/mode_choice_policy.json` |
| `exp_mnl_jtir_nosim` | `scripts/progedo_logit/mnl_model.json` |
| `exp_klr_jtir_nosim` | `scripts/progedo_logit/klr_model.json` — régression logistique à noyau |
| `exp_rf_jtir_nosim` | `scripts/progedo_logit/rf_mode_choice_policy.json` |

La **régression logistique à noyau** (ticket 043) fait bien partie du lot : l'auteur l'a demandée
explicitement, et elle y était depuis la première rédaction. Deux précautions la concernent.
**Les deux précautions annoncées tombent, vérification faite le 2026-09-11.** `klr_model.json` a
bien été réestimé le 11 septembre à 11:28, après l'exécution de 09:31, mais **l'empreinte n'a pas
changé** : les quatre artefacts modèles portent sur le disque exactement le sha256 enregistré dans
leur exécution, KLR compris. La réestimation a réécrit les mêmes octets. `exp_klr_jtir_nosim` se
rejoue donc pour la cohorte, comme les trois autres, et pour aucune autre raison. Quant au statut
de `ticket_043`, il est **déjà `terminé`** dans `tickets_status.yaml` : la question est close.

**Lot 4c — prompt minimal, un bras par modèle ayant produit une mesure complète (6 bras, payants)**

| Modèle | Accès | Mesure v1 de référence | Réglage |
|---|---|---|---|
| `claude-opus-4.6` | antigravity | complète sous `prompt_minimal` | attente 600 s |
| `gemini-3.8-flash` | antigravity | complète sous `prompt_minimal` | attente 120 s |
| `gemini-3.5-flash-lite` | passerelle | complète sous `prompt_minimal` | attente 120 s |
| `gemini-3.1-flash-lite` | passerelle | complète sous `prompt_minimal` | attente 120 s |
| `mistral-large-2512` | passerelle | complète sous `prompt_minimal` | attente 120 s |
| `mistral-small-latest` | passerelle | complète, mais sous `minimal_persona` (invalidé) | attente 120 s |

Tous à `temperature: 0.0`, `top_p: 1.0`, `max_tokens: 4096`. `mistral-small-latest` n'a jamais été
mesuré sous le prompt minimal en service : son bras est neuf, non une répétition.
`gemini-3.1-flash-lite-preview` est **écarté** par décision de l'auteur — seul le modèle stable
`gemini-3.1-flash-lite` est retenu.

**Lot 4d — prompts experts : gardés, aucune expérience planifiée**

Décision de l'auteur, 11 septembre : les variantes `expert_chaine`, `expert_chaine_m5`, `m6`, `m7`
et `m7.1` **restent en place** dans `prompts.yaml` — ni archivées, ni retirées du service, et la
variante active de la catégorie ne change pas. Mais **aucun bras expert n'est planifié dans ce
ticket** : la reconstruction se limite aux planchers, aux oracles et au prompt minimal.

Conséquence à connaître : tant que ce lot n'est pas joué, l'ablation n'a **pas** de palier
« prompt calibré » mesuré sur la v5. Le chapitre 6 ne pourra pas tester H0 sur la cohorte de
référence avec les seules mesures de ce ticket. C'est une conséquence assumée, pas un oubli — elle
se lève en planifiant les bras experts dans un ticket ultérieur, sur un substrat désormais propre.

**Lot 4e — le 2×2 chaîne / anticipation (proposé par l'auteur le 11 septembre)**

L'idée : jouer les familles de référence **deux fois**, avec et sans le schéma de position des
véhicules, et comparer. Elle est juste, et le mécanisme existe déjà — c'est le **lot 1 du
[ticket 040](ticket_040_ablation_filtre_eligibilite_modes.md)**, en veille depuis le 9 septembre :
`VEHICLE_CHAIN_ENABLED=false` et `VEHICLE_RETURN_HOME_LOCK=false`, lus par `AgentConfig`, **aucun
code à écrire**. Trois points avant de lancer.

**a) Ne couper que le lot 1.** « Sans le schéma des voitures » veut dire : position du véhicule
(`vehicule_ailleurs`) et verrou de retour (`retour_force`). **Jamais** la possession, le permis ni
l'âge — ce sont des attributs de la personne, présents dans les 21 variables du contrat
(`number_of_cars`, `has_driving_license`, `has_bike`), que les deux décideurs voient légitimement.
Couper le lot 2 reviendrait à donner une voiture à tout le monde, ce qui ne mesure plus rien.

**b) Prérequis bloquant : l'interrupteur doit entrer dans la définition de l'expérience.**
`reglages_herites` d'une exécution ne porte aujourd'hui que `agenda_anticipation_enabled` et
`max_trip_candidates` — **pas** `vehicle_chain_enabled`. Deux exécutions ne différant que par ce
drapeau porteraient donc la même définition, la même signature, le même nom, et rien dans leur
trace ne dirait laquelle est laquelle. C'est **exactement** le défaut audité aujourd'hui, dans un
autre endroit. L'interrupteur devient un champ de `experience.yaml`, entre dans le nom (règle N7) et
dans `reglages_herites`, avant le premier lancement.

**c) L'anticipation de l'agent ne se coupe pas.** La question a été posée et **tranchée par
l'auteur le 11 septembre : non**. Le drapeau `agenda_anticipation_enabled` existe et permettrait de
mettre l'agent sur le pied informationnel du modèle tabulaire, mais c'est précisément la capacité
pour laquelle des agents sont employés — faire ce qu'un modèle trajet-par-trajet ne peut pas. La
retirer reviendrait à évaluer l'agent en le privant de ce qu'on veut démontrer.

Conséquence à assumer dans l'écriture, non dans le protocole : la comparaison agent / oracle n'est
pas « même information, règle de décision différente », mais **« information supplémentaire et règle
différente »**. C'est l'objet de l'alerte A6a — la règle 1 du contrat doit le dire. Et c'est ce qui
donne son rôle à chacune des deux lectures : l'oracle **hors chaîne** est le plafond
**distributionnel** honnête, celui de la tâche pour laquelle il a été ajusté ; l'oracle **en
chaîne** est sa lecture **opérationnelle**, handicapée par une anticipation qu'il ne peut pas faire.
H0 se teste contre le premier, le second dit ce que coûte l'absence de prévoyance.

Plan proposé, presque entièrement gratuit :

| Condition | Bras | Coût |
|---|---|---|
| chaîne active (nominal) | 4 familles statistiques + 3 planchers | gratuit |
| chaîne coupée (lot 1 du ticket 040) | les mêmes 7 | gratuit |

Quatorze exécutions, **aucun appel de modèle de langue**. L'écart entre les deux lignes chiffre ce
que la contrainte de chaîne impose à un décideur qui ne l'anticipe pas. Les bras LLM ne sont joués
qu'en chaîne active : leur anticipation reste entière, c'est ce que l'article démontre. Le
ticket 040 sort alors de veille, ou ce lot le remplace — à trancher pour qu'un seul des deux porte
la mesure.

**Non reconstruits** — mesure v1 incomplète, cause de bord et non de fond : `gemma-4-31b`,
`gpt-oss-120b` (deux tentatives), `meta/muse-glimmer` (deux), `qwen/qwen3.6-27b` (deux),
`qwen/qwen3.8-27b`, `claude-opus-4.6` sous `minimal_persona`, `gemini-3.1-flash-lite` sous
`prompt_minimal` (première tentative et quatrième, 0,899), `gemini-3.5-flash-lite` sous
`expert_chaine_m5` (première tentative). Plus les 10 définitions jamais exécutées
(`google-g-4-e`, `mistral-7b-v`, `mistral-n-24`, `mistral-s-32`, `qwen3-v-32b`, `qwen3-v-8b-m`,
`qwen36-27b`, `qwen38-27b-l`, et les deux doublons de nommage archivés le 10 septembre).

### Lot 5 — fermer la cause racine pour de bon

- Le nom d'une expérience cesse d'être muet sur sa population : retirer `population` de
  `DEFAUTS_NOMMAGE`, ou n'y laisser muette que la **dernière** cohorte scellée. Un substrat ne doit
  jamais être implicite dans le nom d'une mesure.
- Le tableau de bord affiche l'empreinte de la population **à côté du bouton de lancement**, pas
  seulement dans la synthèse écrite après coup.
- Une garde de cohérence au lancement : si la population de la définition n'est pas celle du jeu
  désigné, refus. Les deux empreintes existent déjà dans les deux manifestes.

## Hors périmètre

- Le choix de l'oracle de référence (tickets 042, 043, 044) : ce ticket rejoue les quatre familles
  sur le bon substrat, il n'en désigne aucune.
- La réécriture des prompts. `prompt_minimal` est pris tel qu'il est en service.
- La section 1.3 du chapitre 1 de l'article, traitée à part.
- Le passage à l'échelle et la reprise à chaud.

## Questions ouvertes

Les trois questions initiales sont **tranchées** (2026-09-11) :

1. **L'empreinte des bras Antigravity** — illusion, cf. A2 : même texte, résolution de chemin
   différente entre hôte et conteneur. Corrigé ; leur comparaison aux bras passerelle tient.
2. **A5, périmètre de comparaison** — décision de l'auteur : **les deux**, publiés côte à côte.
   « Mieux vaut trop d'info que pas assez. » Les parts « toutes décisions » portent la conclusion,
   les parts hors itinéraire unique et le compte de choix forcés les accompagnent, et la
   comparaison terme à terme se fait sur l'intersection des situations que tous les bras ont
   réellement décidées.
3. **Le statut du ticket 043** — déjà `terminé`, rien à faire.

Quatre autres, soulevées par le balayage, ont été tranchées le 2026-09-11 en seconde passe :

- **La règle 1 du contrat d'évaluation est fausse** (A6a) — passée au
  [ticket 046](ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md), qui examine
  quatre options et les chiffre : aligner l'agent sur les variables communes, double mesure avec
  et sans anticipation, déclarer l'asymétrie et en faire l'objet de l'étude, deux lectures pour
  les modèles tabulaires. **En attendant, on reste en l'état** : l'agent garde son anticipation
  et ce ticket continue sans attendre cette réponse.
- **Lot 4e contre ticket 040** — le **040 est clos au profit du 045**. Le prérequis qu'il avait
  identifié (tracer l'état des filtres dans la définition et le nom) est livré ici par R13.
- **`ratios_du_plan()`** — corrigé, et le défaut était plus grave qu'annoncé. Ce n'était pas
  seulement le dernier repli de l'estimation de coût : c'est devenu le **seul**, le repli
  précédent étant la médiane des exécutions archivées, et la base étant désormais vide. Un bras
  payant s'estimait donc « aucune mesure disponible », au moment précis où l'on décide de
  dépenser — défaut **latent hier, actif aujourd'hui du seul fait de l'archivage**. Le chemin est
  corrigé, une absence se journalise, et le plan est monté en lecture seule dans le conteneur,
  qui ne voyait pas `docs/` du tout.
- **Les quatre mesures v1 étiquetées `gemini-3.1-flash-lite`** portaient en réalité la version
  `-preview`, désormais écartée. Le bras stable du lot 4c est donc **neuf**, au même titre que
  `mistral-small-latest`.

Reste vivant, hors de ce ticket : la **variabilité inter-graines**, différée, qui conditionne la
lecture de la double mesure envisagée par le ticket 046.
