# Ticket 071 — Plan d'architecture du volet CODE

> Écrit le 2026-09-14, avant toute ligne de code, conformément à la règle plan-first.
> **Validé le 2026-09-14. Lot 0 livré ; lots 1 à 4 à venir, un par un.**
>
> Les six questions vivantes sont tranchées : voir [`questions.md`](questions.md).
>
> Périmètre de ce plan : le **volet CODE seul** (§ 2 du ticket), soit les lots 1 à 4 et le
> reliquat du § 2.7. Le volet ARTICLE (§ 3) est sous verrou et n'est pas couvert. Le volet
> PLANCHES (§ 4) et le dépôt des PDF (§ 3.4) sont des tâches distinctes, hors code, traitées
> séparément.

---

## 0. Ce que l'exploration du code a établi

Sept points vérifiés dans le dépôt, qui commandent le plan.

| Constat | Où | Conséquence |
|---|---|---|
| `MemoryEntry` est un `dataclass` à 7 champs, sérialisé par `asdict()` et relu par `from_dict(**data)` | `llm/memory.py` | Tout champ ajouté doit avoir un défaut, sinon les métadonnées écrites avant le ticket ne se relisent plus |
| Le vivier unique passe par `shared_index.as_retriever()` avec un filtre `person_id` | `llm/longterm.py:465` | Les viviers B et C n'ont pas besoin de l'index : toutes les entrées de l'agent sont déjà en RAM dans `user_metadata[pid]["entries"]` |
| Le modèle de plongement est en dur | `llm/longterm.py:163` | `settings.agent.embedding_model` existe et n'est lu nulle part — confirmé, une seule occurrence |
| Le retard d'arrivée est déjà calculé | `text_helper/models/arrival.py`, propriété `late` | Composante 1 de `I_det` : disponible |
| La correspondance ratée est un code d'observation | `tc_timeout` → `EnvObTcTimeout` | Composante 2 de `I_det` : disponible |
| Le mode contraint est déjà tracé | `vehicle_chain.py`, motifs `vehicule_ailleurs` / `retour_force` | Composante 4 de `I_det` : disponible |
| L'incident réseau **n'est pas joué par GAMA** | `experiences/experience.py:624` | Composante 3 de `I_det` : **aucun observable**. Voir § 6, question Q1 |

Le déclenchement de la réflexion vit dans `simulation_controller.py:1507-1590` : seuil volumétrique
plus plancher journalier, les deux additifs. C'est là que la gravité cumulée s'insère.

---

## 1. Lot 0 — Les constantes et le câblage des paramètres ✅ LIVRÉ le 2026-09-14

**Fichiers** : `settings.py`, `experiences/cli.py`, plus deux fichiers de tests.

Douze constantes déclarées dans `AgentConfig`, aux valeurs du § 2.10 du ticket, chacune avec sa
règle de conception en commentaire : `memoire__force_k_importance` (6), `force_delta_rappel_jours`
(1 j), `force_max_jours` (30 j), `purge_seuil_poids` (0,01), `retard_ref_s` (1800),
`importance_choc` (0,7), `theta_gravite_cumulee` (0,7), `confiance_seuil_service` (0,5),
`contre_exemples_seuil` (3), `vivier_b_par_mode` (8), `vivier_c_taille` (5),
`fenetre_age_max_jours` (60). Aucune n'a encore de lecteur : elles en gagnent un lot par lot.

**Les cinq poids du rappel.** Les deux nouveaux — `importance_weight` et `affinite_weight`, 0,20
chacun — sont déclarés. Les trois existants **gardent leurs valeurs en service**, 0,4 / 0,3 / 0,3.

> ⚠ **Écart assumé avec le plan initial, qui les faisait passer à 0,30 / 0,10 / 0,20 dès le lot
> 0.** `rank_nodes` n'en lit que trois : les basculer maintenant ferait tomber la somme des poids
> **lus** à 0,60. Comme les composantes entrent en valeur absolue depuis le ticket 048 — la
> normalisation min-max a justement été supprimée pour rendre deux décisions comparables —
> l'ordre des candidats changerait sous un régime de score que personne n'a spécifié. Les cinq
> basculent ensemble, au lot 2. Un test verrouille l'invariant : la somme des poids réellement
> lus par le classement vaut 1, quel que soit le lot en cours.

**La fenêtre d'âge du rappel suit désormais l'horizon de l'expérience**, plafonnée à 60 jours.
`AgentConfig.fenetre_age_pour_horizon` calcule, `experiences.cli.appliquer_fenetre_age` applique
et l'annonce au lancement. C'est le seul comportement que le lot 0 change, et il corrige un défaut
réel : à 30 jours en dur, un run de soixante perdait son second mois sans qu'aucune ligne ne le
dise.

**Reliquat du § 2.7, tranché.** `memory_decay_lambda` vit dans `experiments.yaml`, le plan
scientifique, que le lanceur ne lit pas. **Aucun champ λ n'est ajouté** au modèle d'expérience :
`nom_canonique` calcule la signature d'une définition sur `model_dump()`, si bien qu'un champ de
plus changerait le nommage canonique et la règle « une copie qui ne change rien porte le nom de
sa source ». Reste vrai, et à corriger côté fiche : `exp_04a` déclare un λ que le code n'applique
pas.

**Tests** : 22 dans `test_071_lot0_constantes.py`, 8 fonctionnels dans `test_071_lot0_chaine.py`.
Le test central échoue bien sous le régime d'avant, vérifié en forçant le plafond à 30 jours.

---

## 2. Lot 1 — Qualifier le souvenir

### 2.1 Structure

**Fichier** : `llm/memory.py`.

`MemoryEntry` gagne huit champs, tous avec un défaut, tous optionnels au rechargement :

```python
importance: float = 0.0            # [0, 1]
valence: str = "neutre"            # negative | neutre | positive
axe_objet: Optional[str] = None    # velo, metro_A, bus_401 — normalisé à l'écriture
axe_lieu: Optional[str] = None
axe_creneau: Optional[str] = None  # nuit | matin | midi | soir
axe_motif: Optional[str] = None    # travail, ecole, loisir
force: Optional[float] = None      # jours ; None = jamais qualifié → S0 au rappel
rappels: int = 0
```

Les concepts portent quatre champs de plus, groupés dans un sous-objet `concept` pour ne pas
alourdir les entrées épisodiques : `panier`, `observations`, `contre_exemples`, `depasse_le`.

`from_dict` doit ignorer les clés inconnues au lieu de faire `cls(**data)` : sans ça, revenir en
arrière sur ce ticket rendrait toutes les métadonnées illisibles. C'est une garantie de
réversibilité, pas une commodité.

### 2.2 Gravité déterministe

**Fichier neuf** : `services/llm-agents/llm/gravite.py`. Une fonction pure, testable sans
simulateur ni modèle.

```python
def gravite_deterministe(retard_s, correspondance_ratee, incident_reseau,
                         mode_contraint) -> tuple[float, dict]:
    ...
```

Elle rend la valeur **et le détail des composantes**, pour que l'instrumentation puisse dire
laquelle a contribué. Formule du ticket, sans écart :

```
0,50 × min(retard_s / RETARD_REF, 1)
+ 0,20 × correspondance_ratee
+ 0,20 × incident_reseau
+ 0,10 × mode_contraint
```

Les entrées sont alimentées à l'écriture de la mémoire courte, dans
`simulation_controller._handle_observation` :

| Composante | Source | État |
|---|---|---|
| retard | `parse_ob("arrival").late` | disponible |
| correspondance ratée | `env_ob_code == "tc_timeout"` | disponible |
| incident réseau | — | **aucune source**, voir Q1 |
| mode contraint | contrainte de chaîne `retour_force` / `vehicule_ailleurs` | disponible |

**Point de vigilance, à traiter explicitement.** Une composante sans observable contribue 0, et
0 est la valeur d'un trajet parfait. La gravité serait donc silencieusement sous-estimée sans
qu'aucun symptôme n'apparaisse. Le code doit **déclarer l'inactivité** : un journal au démarrage
disant quelles composantes de `I_det` sont actives, et un compteur de la part des entrées où
chaque composante a pu être évaluée. Une composante inactive n'est pas une composante nulle.

### 2.3 Niveau nommé, jugé par le modèle

**Fichiers** : `packages/mobility_llm/src/mobility_llm/categories/stm_reflection/output_schema.json`
et `template.md.j2`.

Le format des concepts passe du 5-uplet au 5-uplet plus deux champs. Pour ne pas casser
`llm_agent.reflect_on_short_term_memory`, qui fait `json.loads(entry.content)` puis `concept[0]`,
le concept devient un **objet** et non un tableau :

```json
{"contenu": "...", "mots_cles": "...", "portee_spatiale": "...",
 "portee_temporelle": "...", "objet": "...",
 "niveau": "anodin|notable|genant|grave|marquant", "valence": "negative|neutre|positive"}
```

La lecture doit accepter **les deux formes** pendant la transition : un run repris (`CONT=1`)
relit des concepts écrits à l'ancien format.

Le gabarit gagne la grille des cinq échelons, ancrée par conséquence observable, telle qu'écrite
au § 2.1 du ticket. Le rang ne départage qu'à ±0,05 à l'intérieur d'un niveau.

**Règle de sécurité** : `I_concept = max(I_llm, max(I_det du groupe consommé))`. Le groupe
consommé est déjà disponible — `get_all_message_and_group()` rend les entrées groupées par
activité, et ce sont elles qui portent `I_det`.

### 2.4 Durée de vie et renforcement

**Fichier** : `llm/longterm.py`.

```
force = min(S0 × (1 + k × importance), FORCE_MAX)          # à l'écriture
force ← min(force + δ, FORCE_MAX) ; rappels += 1           # à chaque rappel servi
score_temps = exp(-Δt / force)                             # Δt depuis le DERNIER RAPPEL
```

Le passage « depuis le dernier rappel » impose un champ de plus, `dernier_rappel`, distinct de
`timestamp` : le `timestamp` reste l'heure de l'événement, qui s'affiche dans le prompt, et ne
doit surtout pas bouger au rappel. Ce champ manque à la spécification ; je le propose.

Le renforcement s'applique **aux seules entrées effectivement servies au modèle**, c'est-à-dire au
top-K final de `aquery_user_memories`, et non aux candidats. Écriture différée par le mécanisme
`_dirty` existant, pas de flush synchrone sur le chemin de décision.

### 2.5 Déclenchement par gravité cumulée

**Fichier** : `simulation_controller.py`, fonction `_stm_eligible`.

Une troisième condition s'ajoute aux deux existantes, sans les remplacer :

```
somme des I_det du tampon ≥ Θ  →  éligible, motif « rupture »
```

La ligne de journal existante compte déjà les éligibles par seuil et par plancher ; elle gagne un
troisième compteur. L'instrumentation du § 2.10 du ticket demande de **vérifier que ce régime
reste exceptionnel** : moins d'un déclenchement par agent et par semaine. Une alarme sur front
montant se déclenche au-delà.

---

## 3. Lot 2 — Rappeler

**Fichier** : `llm/longterm.py`, plus `agents/llm_agent.py` pour la liste des modes offerts.

### 3.1 Normalisation des axes, à l'écriture

Fonction `normaliser_axes(context, observation)` dans `llm/gravite.py` ou un module frère.
`axe_creneau` réutilise les tranches déjà en service (`categorize_date_time_short`), `axe_motif`
vient de `activity.purpose`, `axe_objet` de `mode_label()` ramené à un mode canonique, `axe_lieu`
de l'arrêt ou de la ligne quand l'observation en porte un. Un axe non résolu vaut `None`, traité
comme absence de correspondance et jamais comme correspondance universelle.

⚠ `mode_label()` est lu par `parse_option_modes` dans le texte du prompt : la normalisation
d'axes ne doit **pas** modifier cette étiquette, seulement en dériver une valeur d'axe à côté.

### 3.2 Les trois viviers

| Vivier | Implémentation proposée | Coût |
|---|---|---|
| A — sémantique | inchangé, `as_retriever` avec filtre `person_id` | un plongement de requête |
| B — par objet | **lecture directe de `user_metadata[pid]["entries"]` en RAM**, filtre `axe_objet ∈ modes offerts`, tri gravité puis récence, 8 par mode | nul |
| C — chocs | même source, filtre `importance ≥ memoire__importance_choc`, 5 au plus | nul |

Le choix de lire la RAM plutôt que d'interroger Chroma par filtre de métadonnées est délibéré :
les entrées d'un agent y sont déjà chargées (cache LRU de 2 000 agents, au-dessus des 1 000
agents de la cohorte), la lecture est O(n) sur quelques centaines d'entrées, et cela évite
d'ajouter des clauses `where` à un magasin dont les capacités de filtrage numérique restent à
vérifier. Déduplication par `doc_id`, puis classement commun.

**Réserve levée le 2026-09-14, après vérification.** Le plan craignait qu'un agent évincé du
cache LRU ne rende des viviers B et C vides. **Ce n'est pas le cas** :
`aquery_user_memories` appelle `ensure_user_initialized` en entrée, qui **recharge les
métadonnées depuis le disque** quand l'agent n'est plus en RAM. Un agent évincé paie une lecture
de fichier, il ne perd pas ses souvenirs. Il reste à **compter les rechargements** : au-delà de
quelques-uns par décision, le plafond LRU est mal dimensionné et chaque décision paie un
aller-retour disque — c'est un problème de coût, pas de justesse.

### 3.3 Les cinq composantes

`rank_nodes` passe de trois à cinq termes, toutes en valeur absolue sur [0, 1] :

```
score = 0,30 × similarité
      + 0,10 × affinité catégorielle     (remplace le « BLEU-2 »)
      + 0,20 × poids temporel            (exp(-Δt/force) si épisodique, confiance si sémantique)
      + 0,20 × gravité
      + 0,20 × affinité d'axes
```

```
affinite_axes = 0,50 × [objet concorde] + 0,20 × [lieu] + 0,15 × [creneau] + 0,15 × [motif]
```

L'affinité est un bonus : un axe discordant vaut zéro, jamais un veto. Hors identité de l'agent
et fenêtre d'âge, rien ne filtre.

Le terme lexical actuel (`_bleu_score`) est **conservé comme fonction** mais n'est plus câblé sur
le score : il devient un appariement d'attributs discrets (mode, créneau, motif, météo). Les
tests existants de `test_071_rappel_et_nettoyage.py` qui le visent restent valides sur la
fonction, et de nouveaux tests visent le nouveau terme.

### 3.4 Le plongement

✅ **Tranché le 2026-09-14 : le dispositif passe à 100 % anglais** (prompts, population,
souvenirs). Le passage à un modèle francophone est **abandonné** : l'argument qui le fondait —
des souvenirs en français lus par un plongement anglophone — tombe avec la bascule, et le modèle
hérité de Vu et al. redevient cohérent avec le corpus.

Reste **un seul geste**, qui ne dépend pas de la langue : brancher
`settings.agent.embedding_model`, aujourd'hui déclaré et relié à rien, le modèle étant codé en
dur. Un paramètre qui ne commande rien empêche de comparer deux modèles sans toucher au code.
Aucune reconstruction d'index n'est nécessaire tant que le modèle ne change pas.

---

## 4. Lot 3 — Consolider les concepts

**Fichiers** : `llm/longterm.py`, schéma et gabarit de `stm_reflection`.

- **Panier** : clé `(axe_objet, axe_motif)`, correspondance exacte sur une métadonnée. Désigne un
  petit ensemble de concepts candidats, jamais un emplacement unique.
- **Discrimination par le modèle** : les concepts du panier lui sont montrés dans l'appel de
  réflexion qui a déjà lieu. Le schéma de sortie gagne `operation ∈ {creer, confirmer, preciser,
  contredire}` et `concept_vise` (identifiant, ou vide).
- **Compteurs** : `observations`, `contre_exemples`, `depasse_le` (date).
- **Confiance** : `(obs + 1) / (obs + contre_ex + 2)`, règle de Laplace.
- **Service** : un concept de confiance < 0,5 cesse d'être servi, **sans être supprimé**.
- **Dépassement** : marqué dépassé à `contre_exemples ≥ 3` **et** confiance < 0,5.
- **Aucune suppression** : c'est la mise à l'écart datée qui est l'observable.

Le panier doit être **stable d'un run repris à l'autre** : la clé se calcule depuis les axes
normalisés, qui sont écrits une fois, jamais recalculés à la lecture.

**Effet de bord signalé par le ticket, à vérifier** : toute modification du schéma de sortie
invalide la mémoïsation par prompt exact (`ReflectionMemoStore`, ticket 012). Le cache de
réflexions accumulé devient inutilisable. Ce n'est pas un bug, c'est un coût : il doit être
annoncé dans le changelog, et la clé de mémoïsation doit porter une **version de schéma** pour
que l'ancien cache soit ignoré plutôt que servi de travers.

---

## 5. Lot 4 — La mémoire noyau

**Fichiers** : `agents/llm_agent.py`, schéma et gabarit de `ltm_self_reflection`.

`query_past_experiences_for_travel` cesse de rendre dix souvenirs bruts et rend un bloc structuré
plus deux ou trois entrées épisodiques :

```
Mes habitudes              ← produit par le JOURNAL DES TRAJETS (moves.csv / MoveLogger)
Ce que je sais             ← produit par la réflexion, chaque énoncé avec son compteur d'obs.
Ce qui a changé récemment  ← produit par la réflexion
```

**Garde-fou non négociable** : le bloc des habitudes est calculé depuis le journal, jamais écrit
par le modèle — un bloc calculé reste vérifiable contre sa source, un bloc réécrit ne l'est plus.
Seul le bloc de connaissances est confié au modèle.

**Aucune métadonnée sur le bloc** : ni date de mise à jour, ni nombre de jours de vécu.

L'auto-réflexion longue durée tourne déjà tous les trois jours ; seule la forme de sa sortie
change, aucun appel supplémentaire.

---

## 6. Questions vivantes

✅ **Les six sont tranchées par l'auteur le 2026-09-14.** Le détail, le raisonnement et ce qui a
été écarté vivent dans [`questions.md`](questions.md). En résumé :

| | Question | Rendu |
|---|---|---|
| Q1 | « incident réseau » sans observable | chaîne complète prévue, composante non alimentée, **inactivité déclarée** au journal |
| Q2 | conflit 071 / 074 sur le plongement | **100 % anglais** ; Solon abandonné, seul le paramètre est branché |
| Q3 | champ `dernier_rappel` manquant | accepté, champ distinct au lot 1 |
| Q4 | λ dans le plan scientifique | **ne pas ajouter le champ** ; seul l'horizon est câblé |
| Q5 | mesure de Θ sur run GAMA | instrumentation au lot 1, run ensuite |
| Q6 | ordre de livraison | **lot par lot**, chacun laissant le dépôt exécutable |

Décision connexe : **l'article passe en toute fin**, quand le code a cessé de bouger.

## 7. Tests

**Exigence de l'auteur, 2026-09-14 : des tests FONCTIONNELS, avec doublures sur toute la chaîne.**
Pas seulement des vérifications de valeurs. Deux fichiers par lot :

- `..._constantes.py` — ce qui doit rester vrai : valeurs publiées, invariants de conception ;
- `..._chaine.py` — ce qui doit se produire, à travers les mêmes appels que la production, avec
  l'index vectoriel, le modèle de plongement et la passerelle LLM doublés.

Règle de tenue : **un test doit échouer sur le comportement d'avant**. Un test qui passe des deux
côtés du changement ne prouve rien.

| Lot | Ce que la chaîne doit montrer, doublures comprises |
|---|---|
| 0 ✅ | définition d'expérience doublée → réglage → rappel : le second mois d'un run de 60 jours est de nouveau servi, un horizon de 5 jours referme la fenêtre, un autre agent n'est jamais exposé |
| 1 | observation d'arrivée doublée → gravité déterministe → durée de vie → réflexion déclenchée par rupture. Réponse du modèle doublée pour le niveau nommé, règle du maximum vérifiée contre un retard mesuré |
| 2 | trois viviers réunis et dédupliqués, cinq composantes, affinité en bonus et jamais en veto : une chute à vélo du matin atteint la décision du soir, alors qu'aucun axe ne concorde |
| 3 | réflexion doublée émettant les quatre opérations : compteurs, confiance de Laplace, mise hors service sous 0,5, dépassement à trois contre-exemples, **jamais de suppression** |
| 4 | journal de trajets doublé → bloc d'habitudes : le bloc vient du journal et non du modèle, et ne porte aucune métadonnée sur lui-même |

Les dix-sept tests de `test_071_rappel_et_nettoyage.py` et les trente du lot 0 sont le filet de
non-régression. ⚠ La suite de `services/llm-agents` embarque `pytest-randomly` : l'ordre varie
d'un lancement à l'autre et expose des dépendances d'ordre **préexistantes** dans les tests 035,
045 et agenda. Avec `-p no:randomly` elle est verte et déterministe.

## 8. Documentation à mettre à jour, à chaque lot

- `docs/arch/memory-stm-ltm.md` — **replier la partie III dans la partie II au fur et à mesure**,
  c'est un critère de clôture explicite du ticket.
- `docs/changelog.md` — une entrée par lot, en haut, format `## [AAAA-MM-JJ] Titre fonctionnel`,
  avec bloc Avant / Après.
- `docs/tickets/ticket_071_*.md` — la table du § 2.0 « déjà livré » s'allonge.
- `scripts/dashboard/tickets_status.yaml` — seule source de vérité du statut.
- Signalement `article-impact` en fin de tâche : les lots 1 à 4 touchent des métriques et des
  comportements décrits dans l'article. Le signalement s'arrête au constat ; la correction
  repasse par le verrou.
