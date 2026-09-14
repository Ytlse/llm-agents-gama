# Ticket 071 — Questions vivantes

Ouvertes le 2026-09-14 au moment du plan d'architecture. **Les six sont tranchées par l'auteur
le même jour.** Conservées avec leur raisonnement : ce qui a été écarté devra être tenu devant
un relecteur.

---

## Q1 — La composante « incident réseau » de `I_det` n'a aucun observable

`experiences/experience.py` déclare un format d'événement `incident`, mais le code refuse
l'exécution : les événements ne sont pas encore joués par GAMA. La formule de gravité
déterministe lui donne pourtant 20 % du poids.

✅ **Rendu 2026-09-14 : la chaîne complète est prévue, la composante n'est pas encore alimentée.**
Le paramètre traverse toute la chaîne — signature de la fonction de gravité, champ d'entrée,
compteur d'instrumentation, journal — et vaut zéro tant que GAMA ne joue pas les incidents. Le
jour où l'événement arrive, il n'y a qu'une source à brancher, pas une formule à rouvrir.

**Garde-fou exigé :** l'inactivité se **déclare**. Un journal au démarrage dit quelles composantes
de `I_det` sont actives, et un compteur dit sur quelle part des entrées chacune a pu être évaluée.
Sans cela, une composante sans observable contribue zéro, et zéro est déjà la valeur d'un trajet
parfait : la gravité serait sous-estimée sans qu'aucun symptôme n'apparaisse. Les trois autres
composantes ne sont **pas** repondérées — repondérer changerait l'échelle de gravité en silence.

---

## Q2 — Conflit 071 / 074 sur le modèle de plongement

Le ticket 071 passait le plongement à `Solon-embeddings-large-0.1`, francophone. Le ticket 074
bascule le dispositif en anglais. Les deux imposent une reconstruction d'index, en sens opposés.

✅ **Rendu 2026-09-14 : 100 % anglais — prompts, population, souvenirs.** Le passage au
francophone est **abandonné**. L'argument qui le fondait — « les souvenirs sont en français, le
plongement est anglophone » — tombe avec la bascule : le modèle anglophone hérité de Vu et al.
redevient cohérent avec le corpus.

**Ce qui reste à faire au lot 2, et qui ne dépend pas de la langue :** brancher
`settings.agent.embedding_model`, aujourd'hui déclaré et relié à rien. Un paramètre qui ne
commande rien empêche de comparer deux modèles sans toucher au code.

**Conséquence sur l'article :** la référence MTEB-French sort du § 3.3, et le rang de Solon n'a
plus à être recoupé.

---

## Q3 — Un champ `dernier_rappel` manque à la spécification

La décroissance doit partir du dernier rappel. Mais `MemoryEntry.timestamp` s'affiche dans le
prompt et sert de côté gauche aux filtres par jour et par ancienneté : le faire bouger au rappel
réécrirait l'histoire de l'agent.

✅ **Rendu 2026-09-14 : accepté.** Champ distinct `dernier_rappel`, reporté dans
`memory-stm-ltm.md` partie III au lot 1.

---

## Q4 — Le λ du § 2.7 vit dans le plan scientifique, pas dans la plateforme

✅ **Rendu 2026-09-14 : ne pas ajouter le champ λ.** Seul le câblage
`horizon_jours → long_term_max_days_query` est fait, et il l'est au lot 0.

**Raison technique qui appuie ce rendu :** ajouter un champ à `Experience` changerait la
**signature** des définitions — `nom_canonique` la calcule sur `model_dump()` — donc le nommage
canonique, et la règle « une copie qui ne change rien porte le nom de sa source ».

**Reste vrai :** le bras `exp_04a` déclare `memory_decay_lambda: 0.4` dans `experiments.yaml`,
que le lanceur ne lit pas. C'est une fiche que le run ne respecte pas. La correction passe par la
fiche, pas par le code.

---

## Q5 — Le rang 2 de l'ordre d'exécution demande un run GAMA

✅ **Rendu 2026-09-14 : l'instrumentation est livrée au lot 1, le run vient ensuite.**

**Ce que cette mesure est, précisément.** Θ vaut 0,7 et déclenche une réflexion *en cours de
journée* dès que les gravités accumulées dans le tampon d'un agent atteignent ce seuil. Ce régime
doit rester l'**exception** : le régime de base est le plancher de 22 h. Mais personne ne sait
aujourd'hui à quelle fréquence 0,7 est franchi, parce que `I_det` n'existe pas encore et qu'aucun
run ne l'a jamais calculé.

**Ce qu'il faut mesurer :** la distribution de `I_det` par agent et par jour simulé, sur un run
GAMA ordinaire. **Le critère :** moins d'un déclenchement par agent et par semaine. Au-dessus, Θ
monte — sinon la consolidation de nuit, qui est le régime choisi, devient l'exception à son tour,
et le coût d'inférence suit.

**Pourquoi ça ne peut pas se faire sur jeux gelés :** un jeu gelé rejoue des décisions
enregistrées, il ne produit pas les observations d'arrivée d'où `I_det` se calcule.

**Ce que le lot 1 livre pour rendre la mesure possible :** les gravités attribuées par cycle en
cinq quantiles, la part des souvenirs au-dessus du seuil de choc, un compteur de déclenchements
par rupture distinct des deux autres motifs, et une alarme sur front montant si le régime cesse
d'être rare.

---

## Q6 — Ordre de livraison

✅ **Rendu 2026-09-14 : livraison par lot.** Chaque lot avec ses tests, sa documentation et son
entrée de changelog, et laissant le dépôt exécutable.

---

## Q7 — Les cinq échelons de gravité varient-ils d'un modèle à l'autre ?

Soulevée par l'auteur le 2026-09-14 : rien ne garantit que `anodin` / `notable` / `genant` /
`grave` / `marquant` soient compris de la même façon par deux modèles différents.

✅ **Rendu 2026-09-14 : les ancres actuelles sont conservées telles quelles.** Une proposition de
les renforcer par des quantités mesurables — « moins de cinq minutes », « plus de quinze minutes
ou une activité manquée » — a été examinée et **écartée** : les ancres par conséquence observable
suffisent. Le gabarit du lot 1 reprendra donc mot pour mot les cinq ancres de
`memory-stm-ltm.md`, partie III.

**Ce qui borne déjà la dérive, et ce qui ne la borne pas.** La règle du maximum,
`I_concept = max(I_llm, max(I_det du groupe consommé))`, empêche un modèle de **sous-estimer** un
incident mesuré : le fait l'emporte sur le jugement. La **surestimation**, elle, n'est bornée par
rien. L'asymétrie est assumée en l'état ; la corriger demanderait un plafond symétrique, qui n'est
pas spécifié et n'est pas ajouté.

✅ **Clos le 2026-09-14 : pas de mesure d'accord inter-modèles.** Décision de l'auteur, et le
plan de campagne la rend sans conséquence sur les chiffres publiés.

**Vérification faite le 2026-09-14 sur `experiments.yaml`.** Une seule expérience de toute la
campagne déclare la mémoire active, `exp_04a_hysteresis_memory_5d`, sur `gemini-3.1-flash-lite`.
Les quatre bras qui font varier le modèle, `exp_01a` à `exp_01d`, ne déclarent pas de mémoire :
ils ne produisent donc aucune réflexion, aucun concept, aucune gravité jugée. **L'échelle des cinq
niveaux n'est exercée que par un seul modèle**, et la variance inter-modèles ne touche aucun
nombre de l'article.

**Ce que cela laisse comme exposition, à dire plutôt qu'à mesurer.** La reproductibilité externe :
un tiers qui rejoue le dispositif avec un autre modèle peut obtenir d'autres gravités. Et toute
expérience future qui activerait la mémoire sous un autre modèle sortirait de ce périmètre sans
qu'aucun garde-fou ne le signale.

**Garde-fou proposé pour le lot 1**, peu coûteux : au lancement, si une expérience déclare la
mémoire active sous un modèle autre que celui de la campagne, le dire. Une ligne de journal, pas
un refus. Sans elle, le jour où ce cas arrive, personne ne le verra.

---

## Décisions connexes, prises le 2026-09-14

- **L'article passe en toute fin.** Aucune écriture dans `docs/paper/article/` avant que le code
  ait cessé de bouger. Le verrou reste entier : diff présenté, accord explicite, un seul accord
  par tâche.
- **Les tests sont fonctionnels, avec doublures sur toute la chaîne**, et pas seulement des
  vérifications de valeurs. Un test doit échouer sur le comportement d'avant.
- **Le rythme de l'auto-réflexion longue durée est déjà un paramètre** :
  `long_term_self_reflect_interval_days`, défaut 3. Rien à faire, sinon ne pas le recoder en dur
  au lot 4.
