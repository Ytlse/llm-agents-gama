# Ticket 071 — Évolution de la mémoire : du code actuel à l'état visé


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
> Ouvert le 2026-09-14.
>
> **Objet.** Ce ticket rassemble **tout ce qui touche à la mémoire des agents et n'est pas encore
> codé**, en trois volets : le **code**, l'**article**, les **planches de présentation**. Il est
> le panel complet de l'évolution, de l'état actuel mesuré à l'état visé.
>
> **Relation aux autres tickets.** Le [051](ticket_051_reflexion_architecture_cognitive_memoire.md)
> instruit les verrous conceptuels et ne fige aucune solution ; le
> [048](ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) porte le calendrier de
> consolidation et l'échelle d'oubli ; le [065](ticket_065_consolidation_etat_de_lart_et_harmonisation_bibtex.md)
> porte le dépôt des PDF et la bibliographie ; le [067](ticket_067_relecture_critique_chapitre_par_chapitre_aamas.md)
> porte la relecture chapitre par chapitre. **Ce ticket-ci est celui de l'exécution** : il dit
> quoi changer, où, et dans quel ordre.
>
> ⚠ **Verrou d'écriture.** `docs/paper/article/` ne s'écrit pas sans accord humain explicite, via
> la skill `article-verrou`, diff présenté et validé. Le volet 2 **décrit** le travail, il
> n'autorise pas à l'exécuter.
>
> ⚠ **Numérotation.** Créé d'abord sous le n° 049, déjà occupé depuis le 2026-09-12 par
> [l'itinéraire mixte](ticket_049_itineraire_mixte_limite_a_publier.md). Renuméroté en 071 le jour
> même, code, tests et documentation compris.
>
> ⚠ **Relecture du 2026-09-14, sur avis extérieur.** Trois remarques d'une relecture extérieure
> sont intégrées : l'ancrage de la somme pondérée dans l'équation d'activation d'ACT-R (§ 2.2),
> un paramètre d'ablation `α` sur la dépendance entre durée de vie et gravité (§ 2.6, arbitrage 1),
> et le plancher journalier comme régime de consolidation (§ 2.6, arbitrage 2). Règle appliquée à
> toute la relecture : **chaque mécanisme porte le travail dont il dérive**, avec l'endroit où ce
> travail le dit ; ce qui ne dérive de personne est écrit **apport propre**. Les notices ont été
> recoupées le 2026-09-14 sur la notice d'éditeur ou d'arXiv (§ 3.3). Deux affirmations de la
> relecture extérieure qui ne tenaient pas devant les sources sont corrigées et non recopiées :
> le contenu de l'activation de base d'ACT-R (§ 2.2) et le coût d'une réflexion par déplacement
> (§ 2.6). Retour de l'auteur le même jour : l'arbitrage 2 est **confirmé**. L'arbitrage 1 est
> **rendu le 2026-09-14, issue C** : le critère de réfutation (ii) du chapitre 7 et le bras
> `exp_04d` sont supprimés, et le paramètre `α` avec eux ; le couplage entre durée de vie et
> gravité est gardé tel quel, sans interrupteur (§ 2.6).

---

# 1. Le panel : d'où l'on part, où l'on va

Spécification de référence : [`docs/arch/memory-stm-ltm.md`](../arch/memory-stm-ltm.md),
partie II pour l'existant, partie III pour la cible.

| Dimension | Aujourd'hui, mesuré | État visé |
|---|---|---|
| Champs d'un souvenir | 7 : contenu, horodatage, type, agent, activité, mots-clés, identifiant de document | **+8** : gravité, valence, quatre axes, force, rappels. **+3** sur les concepts : panier, observations, contre-exemples |
| Gravité d'un souvenir | **inexistante** | déterministe depuis la simulation, plus un niveau nommé jugé par le modèle, le maximum des deux l'emportant |
| Déclenchement de la réflexion | compte de 10 entrées, ou plancher journalier à 22 h | **gravité cumulée**, ou plancher journalier |
| Oubli | `exp(-Δt/2,8)` uniforme pour tous les types, depuis l'**écriture** | épisodique : `exp(-Δt/force)`, force fonction de la gravité, depuis le **dernier rappel**. Sémantique : **confiance**, jamais l'horloge |
| Vivier de candidats | une passe sémantique, 50 candidats | **trois viviers** réunis : sémantique, par objet, chocs |
| Composantes du score | 3, pondérées 0,4 / 0,3 / 0,3 | **5**, pondérées 0,30 / 0,10 / 0,20 / 0,20 / 0,20, le terme lexical devenant une affinité catégorielle |
| Plongement | `all-MiniLM-L6-v2`, anglophone, **codé en dur** | un modèle **anglophone**, via le paramètre branché. ⚠ Cible révisée le 2026-09-14 : `Solon-embeddings-large-0.1` est **abandonné**, le dispositif bascule en anglais (ticket 074) |
| Concepts | empilés, jamais corrigés, contradictions arbitrées à chaque décision | panier de candidats, quatre opérations, compteurs, concepts dépassés marqués et jamais supprimés |
| Ce que le modèle voit | 10 souvenirs bruts | **mémoire noyau** structurée, plus 2 ou 3 épisodiques |
| Rétention | âge et type, en temps simulé | âge, type, **gravité** et **confiance** |

**Contrainte transverse.** Aucun lot ne coûte d'appel supplémentaire au modèle : tout ce que le
modèle produit ici est demandé à l'intérieur des réflexions qui ont déjà lieu.

**Écart relevé à la relecture du 2026-09-14.** Les poids en service, 0,4 sémantique / 0,3 lexical
/ 0,3 temporel (`settings.py`), ne sont pas ceux que Vu, Gaudou & Oberoi (2025, § 4.1) retiennent
après validation manuelle sur cinq agents : `α = 0,3` sémantique, `β = 0,3` BLEU-2, **`γ = 0,4`
récence**. Le poids fort a changé de composante sans que la spécification ni l'article ne le
disent. Ce n'est pas une erreur du code, c'est une divergence non documentée : elle est ajoutée au
§ 3.2 et devra être dite là où l'article citera Vu et al.

---

# 2. Volet CODE

## 2.0 Déjà livré — ne pas refaire

| Livré | Où | Quand |
|---|---|---|
| Plancher journalier de consolidation à 22 h | `simulation_controller.py` | 2026-09-11, ticket 048 |
| Normalisation min-max supprimée, composantes en valeur absolue | `llm/longterm.py` | 2026-09-11, ticket 048 |
| Constante de temps d'oubli en jours, défaut 2,8 | `settings.py` | 2026-09-11, ticket 048 |
| Top-K à 10, cache LRU à 2 000 agents | `settings.py` | 2026-09-11 |
| Nettoyage en temps simulé, avec abandon si indatable | `llm/longterm.py` | 2026-09-14 |
| Suppression dans l'index vectoriel, identifiant monotone | `llm/longterm.py`, `llm/memory.py` | 2026-09-14 |
| Cumul du filtre d'âge et du filtre par jour | `llm/longterm.py` | 2026-09-14 |
| Fin du plafond de 0,70 sur les étiquettes mono-terme | `llm/longterm.py` | 2026-09-14 |
| **Lot 0** — les onze constantes du § 2.10 déclarées, chacune avec sa règle | `settings.py` | 2026-09-14 |
| **Lot 0** — les deux poids nouveaux déclarés (gravité, affinité d'axes), non lus | `settings.py` | 2026-09-14 |
| **Lot 0** — fenêtre d'âge = horizon de l'expérience, plafond 60 j (reste du § 2.7) | `settings.py`, `experiences/cli.py` | 2026-09-14 |
| **Lot 1** — gravité déterministe, niveaux nommés, règle du maximum | `llm/gravite.py` (neuf) | 2026-09-14 |
| **Lot 1** — 9 champs sur `MemoryEntry`, relecture tolérante aux deux sens | `llm/memory.py` | 2026-09-14 |
| **Lot 1** — durée de vie couplée à la gravité, renforcement additif, décroissance depuis le dernier rappel | `llm/longterm.py` | 2026-09-14 |
| **Lot 1** — rétention par le POIDS, sémantique jamais purgé à l'horloge | `llm/longterm.py` | 2026-09-14 |
| **Lot 1** — déclenchement par rupture, compteur des 3 motifs, alarme de rareté | `simulation_controller.py` | 2026-09-14 |
| **Lot 1** — concept objet avec `severity` et `valence`, cinq ancres au gabarit | `stm_reflection/` | 2026-09-14 |
| **Lot 1** — clé de mémoïsation versionnée (l'ancien cache manque au lieu de servir faux) | `llm/reflection_store.py` | 2026-09-14 |
| **Lot 2** — axes normalisés à l'écriture, affinités, appariement sur un ensemble | `llm/axes.py` (neuf) | 2026-09-14 |
| **Lot 2** — viviers B (par objet) et C (chocs), lus en RAM sans plongement | `llm/longterm.py` | 2026-09-14 |
| **Lot 2** — score à CINQ composantes, les cinq poids basculés ensemble à 1,00 | `llm/longterm.py`, `settings.py` | 2026-09-14 |
| **Lot 2** — instrumentation des viviers et ses deux alarmes | `llm/longterm.py` | 2026-09-14 |
| **Lot 2** — `embedding_model` branché (modèle inchangé) | `llm/longterm.py` | 2026-09-14 |
| **Lot 2** — cinquième axe `axe_meteo`, champ `mode` du concept (schéma v2) | `llm/memory.py`, `stm_reflection/` | 2026-09-14 |
| **Lot 3** — panier, quatre opérations, confiance de Laplace, mise à l'écart datée | `llm/concepts.py` (neuf), `agents/llm_agent.py` | 2026-09-14 |
| **Lot 3** — deux régimes d'effacement : le sémantique ne s'oublie plus à l'horloge | `llm/longterm.py` | 2026-09-14 |
| **Lot 3** — concepts hors service écartés du rappel, sans suppression | `llm/longterm.py` | 2026-09-14 |
| **Lot 3** — `operation` et `target_id` au schéma (v3), concepts connus montrés au modèle | `stm_reflection/`, `agents/llm_agent.py` | 2026-09-14 |
| **Lot 3** — compteur d'opérations et alarme « le modèle confirme tout » | `agents/llm_agent.py` | 2026-09-14 |
| **Lots 2 et 3** — 76 tests, contrats écrits avant le code | `tests/test_071_lot2_rappel.py`, `tests/test_071_lot3_concepts.py` | 2026-09-14 |
| **Lot 4** — mémoire noyau : trois blocs CALCULÉS, aucun écrit par le modèle | `llm/noyau.py` (neuf) | 2026-09-14 |
| **Lot 4** — journal des trajets, créé et persisté avec les métadonnées de l'agent | `llm/longterm.py`, `simulation_controller.py` | 2026-09-14 |
| **Lot 4** — le rappel rend le bloc plus 2-3 épisodiques, au lieu de 10 bruts | `agents/llm_agent.py` | 2026-09-14 |
| **Lot 4** — 27 tests, contrat écrit avant le code | `tests/test_071_lot4_noyau.py` | 2026-09-14 |

Les dix-sept tests de `services/llm-agents/tests/test_071_rappel_et_nettoyage.py` passent au
2026-09-14, ainsi que les trente du lot 0 et les quatre-vingt-quatre du lot 1
(`test_071_lot1_gravite.py`, `test_071_lot1_chaine.py`). Suite complète : 971 tests verts.
Spécification de test : `specs/ticket_071/tests_lot1.md`.

✅ **LES QUATRE LOTS DU VOLET CODE SONT LIVRÉS le 2026-09-14**, avec 249 tests de mémoire, tous
verts. Chaque lot a son contrat de test rédigé AVANT son code, dans `specs/ticket_071/`. Validation par l'échec
vérifiée sur les deux lots : rebrancher la décroissance d'horloge sur les concepts casse trois
tests, retirer la règle du maximum en casse deux.

⚠ **Six défauts de la spécification cible ont été trouvés en écrivant ces contrats**, tous
avant le code et tous corrigés : deux dans la formule de départage (lot 1), un double comptage
entre affinité catégorielle et affinité d'axes (lot 2), un conflit entre le rafraîchissement
d'horodatage et la règle du lot 1 (lot 3), une date de mise à l'écart **inatteignable** pour un
concept peu observé (lot 3) — celle-là trouvée en EXÉCUTANT les tests, pas en les lisant — et
l'**absence** du journal des trajets sur lequel le lot 4 s'appuie, qui a dû être créé.

⚠ **Deux tests ont dû changer de règle, et c'est dit ici plutôt que caché** :
`test_le_score_en_service_n_a_pas_bouge` figeait l'état intermédiaire du lot 0, quand le
classement ne lisait que trois poids sur cinq ; il devient
`test_les_cinq_poids_ont_bascule_ensemble`. Et
`test_le_nettoyage_conserve_reflexions_et_resumes` encodait l'exemption par TYPE, que le lot 1
remplace par la rétention au poids. Il est devenu
`test_le_nettoyage_separe_l_episodique_du_semantique`.

⚠ **Ce que le lot 0 n'a délibérément PAS fait.** Les trois poids lus par `rank_nodes` gardent
leurs valeurs en service (0,4 / 0,3 / 0,3) et ne passent à 0,30 / 0,10 / 0,20 qu'avec le lot 2.
Les basculer avant que le classement ne lise les cinq ferait tomber la somme des poids lus à 0,60 ;
les composantes entrant en valeur **absolue** depuis le ticket 048, l'ordre des candidats
changerait sous un régime de score que personne n'a spécifié. Un état intermédiaire non spécifié
ne doit pas être exécutable. Un test le verrouille.

⚠ **Le λ du § 2.7 n'est pas câblé, et c'est une décision.** `memory_decay_lambda` vit dans
`experiments.yaml`, le plan scientifique, que le lanceur ne lit pas ; la plateforme porte
`Experience.memoire` et `Experience.horizon_jours`. Lui ajouter un champ change la **signature**
des définitions — `nom_canonique` la calcule sur `model_dump()` — donc le nommage canonique et la
règle « une copie qui ne change rien porte le nom de sa source ». À arbitrer avant de le faire.

## 2.1 Lot 1 — qualifier le souvenir

**Fichiers** : `services/llm-agents/llm/memory.py`, `llm/longterm.py`,
`urban_mobility_agents/simulation_controller.py`, `settings.py`,
`packages/mobility_llm/src/mobility_llm/categories/stm_reflection/{template.md.j2,output_schema.json}`.

- **Structure.** Ajouter à `MemoryEntry` : `importance` sur [0, 1], `valence` parmi négative,
  neutre, positive, `axe_objet`, `axe_lieu`, `axe_creneau`, `axe_motif`, `force` en jours,
  `rappels` en entier. Les concepts portent en plus `panier`, `observations`,
  `contre_exemples`, `depasse_le`.
- **Gravité déterministe** pour les entrées brutes, calculée depuis les observations que GAMA
  renvoie, sans modèle : `0,50 × min(retard/30 min, 1) + 0,20 × correspondance ratée +
  0,20 × incident réseau + 0,10 × changement de mode contraint`, borné sur [0, 1].
  **Apport propre** : ni Park et al. ni Vu et al. ne disposent d'un simulateur qui mesure le
  retard subi, et Park et al. (2023, § 4.1) écrivent qu'« il existe beaucoup d'implémentations
  possibles d'un score d'importance ».
- **Niveau nommé** pour les concepts, demandé dans la réflexion existante. Cinq échelons ancrés
  sur une conséquence observable : `anodin` 0,10, `notable` 0,30, `genant` 0,50, `grave` 0,75,
  `marquant` 1,00. Raffinement de l'échelle de Park et al. (2023, § 4.1), qui demandent un entier
  de 1 à 10 ancré aux deux extrémités seulement, « se brosser les dents » et « une rupture ».
  Le **rang** ne sert que de départage à l'intérieur d'un même niveau, ±0,05 : un ordre est
  relatif au lot, une valeur doit être comparable d'un jour et d'un agent à l'autre.
  ✅ **Formule de départage corrigée le 2026-09-14**, deux défauts trouvés en rédigeant les tests
  (`specs/ticket_071/tests_lot1.md`, § 9) : le départage vaut **zéro** quand un concept est seul
  dans son niveau — il était pénalisé de 0,05, alors que c'est le cas le plus courant — et `I_llm`
  est **bornée sur [0, 1]** — un `marquant` premier de trois valait 1,05. Rien n'était implémenté,
  aucun code n'est concerné ; formule corrigée dans `memory-stm-ltm.md`, partie III.
  ✅ **Ancres figées le 2026-09-14.** Une proposition de les renforcer par des quantités
  mesurables (minutes perdues, activité manquée) a été examinée et **écartée par l'auteur** : les
  ancres par conséquence observable de `memory-stm-ltm.md`, partie III, sont reprises **mot pour
  mot** dans le gabarit du lot 1. ✅ **Accord inter-modèles : pas de mesure, décision du 2026-09-14.**
  Vérification à l'appui : une seule expérience de la campagne déclare la mémoire active,
  `exp_04a`, sur `gemini-3.1-flash-lite` ; les quatre bras qui font varier le modèle
  (`exp_01a`-`d`) n'ont pas de mémoire et ne produisent donc aucune gravité jugée. **L'échelle
  n'est exercée que par un seul modèle** et la variance inter-modèles ne touche aucun chiffre de
  l'article. Exposition résiduelle à DIRE et non à mesurer : la reproductibilité externe. Garde-fou
  retenu pour le lot 1 : journaliser toute expérience qui activerait la mémoire sous un autre
  modèle (specs/ticket_071/questions.md, Q7).
- **Règle de sécurité, non négociable.** `I_concept = max(I_llm, max(I_det du groupe consommé))`.
  Un modèle qui sous-estime un incident de quarante-cinq minutes ne peut pas le dégrader.
  Apport propre.
- **Durée de vie.** `force = min(S0 × (1 + k × importance), FORCE_MAX)`, avec `S0 = 2,8` jours,
  `k = 6` et `FORCE_MAX = 30` jours, valeurs et règles fixées le 2026-09-14 (§ 2.10). Le paramètre
  d'ablation `α` proposé par la relecture extérieure est **abandonné** (§ 2.6, issue C). La forme `exp(-Δt / force)` et la force
  qui croît au rappel sont celles de MemoryBank (Zhong et al., 2024), qui reprend la courbe
  d'oubli d'Ebbinghaus (1885). **La modulation de la durée de vie par la gravité ne vient pas
  d'ACT-R** : l'activation de base y dépend de la récence et de la fréquence des usages, et de
  rien d'autre (Anderson & Schooler, 1991 ; Anderson & Lebiere, 1998). Elle s'appuie sur la
  mémoire émotionnelle : l'activation émotionnelle renforce la consolidation d'un souvenir
  (McGaugh, 2004). `S0` reproduit exactement la décroissance en service (ticket 048) : un défaut
  plus court accélérerait l'oubli en silence et rendrait inattribuable tout écart mesuré ensuite.
- **Renforcement au rappel.** `force ← min(force + δ, FORCE_MAX)`, `δ = 1` jour, et `rappels += 1` ;
  additif depuis le 2026-09-14, le facteur multiplicatif saturant tout sur soixante jours (§ 2.10).
  Corollaire : la décroissance doit partir du **dernier rappel** et non de l'écriture, comme
  chez Park et al. (2023, § 4.1), dont la récence décroît « depuis le dernier rappel du souvenir ».
  Même principe chez MemoryBank, et dans l'apprentissage de base d'ACT-R, où chaque rappel ajoute
  un terme à `B_i = ln Σ_j t_j^(-d)` (Anderson & Lebiere, 1998) ; la forme additive en `δ`
  est plus simple que la leur, et c'est un choix, pas une équivalence.
- **Déclenchement par gravité cumulée.** Le seuil passe d'un compte d'entrées à une somme de
  gravités, mécanisme de Park et al. (2023, § 4.2), seuil de 150 sur leur échelle de 1 à 10,
  atteint « environ deux ou trois fois par jour ». Ici `Θ = 0,7`, le seuil du choc, pour ne se
  déclencher en journée que sur rupture, le plancher journalier de 22 h restant le régime de
  base (§ 2.6, arbitrage 2).
- **Rétention.** Le nettoyage cesse d'être aveugle : un souvenir de forte gravité, ou un concept
  de forte confiance, survit au seuil d'âge. Apport propre, conséquence du § 2.5.

**Effet de bord à mesurer** : toute modification du schéma de sortie de la réflexion invalide la
mémoïsation par prompt exact (`ReflectionMemoStore`, ticket 012).

## 2.2 Lot 2 — rappeler

**Fichiers** : `llm/longterm.py`, `settings.py`, `urban_mobility_agents/agents/llm_agent.py`.

- **Normaliser les quatre axes à l'écriture**, jamais à la lecture, en résolvant vers un
  identifiant réseau quand c'est possible. Sans cela, deux graphies de la même ligne ne se
  rencontrent jamais. Un axe non résolu vaut « absent », ce qui ne correspond à rien plutôt
  qu'à tout.
- **Trois viviers**, réunis et dédupliqués. **A**, sémantique, comportement actuel conservé.
  **B**, par objet : pour chaque mode offert dans les options, les souvenirs portant cet objet,
  les plus graves et les plus récents d'abord, huit au plus par mode, sans embedding. **C**,
  chocs : les souvenirs au-dessus du seuil de gravité, cinq au plus, sans condition de contexte.
  Génération de candidats multi-viviers, sans filiation revendiquée, la filiation HippoRAG ayant
  été retirée le 2026-09-14. Sa lecture dans ACT-R est celle de l'amorçage associatif : chaque
  élément du contexte courant, le texte de la situation pour **A**, chaque mode offert pour
  **B**, est une source `j` qui active ses souvenirs associés (Anderson et al., 2004) ; **C**
  n'est pas un amorçage mais un accès direct aux souvenirs de forte activation de base.
- **Cinq composantes**, toutes en valeur absolue : similarité 0,30, lexical 0,10, poids temporel
  0,20, gravité 0,20, affinité d'axes 0,20. Poids de départ, à calibrer. Leur ancrage théorique
  est donné ci-dessous.
- **L'affinité est un bonus, jamais un veto.** Un axe discordant contribue zéro. Hors identité de
  l'agent et fenêtre d'âge, **rien ne filtre**. C'est ce qui permet à une chute à vélo du matin
  d'atteindre la décision du soir, alors qu'aucun de leurs contextes ne coïncide. C'est aussi la
  règle de l'appariement partiel d'ACT-R : un attribut discordant applique une pénalité, il
  n'exclut pas (Anderson & Lebiere, 1998). Et c'est la mise en œuvre de la pertinence
  contextuelle « par lieu et heure de la journée » que Vu et al. (2025, § 3.4.3) spécifient sans
  champs typés.
- **Affinité catégorielle à la place du terme lexical.** Le score dit « BLEU-2 » est un taux de
  rappel lexical asymétrique sur les étiquettes, pas le BLEU de Papineni et al. (2002), qui est
  une précision n-gramme modifiée avec pénalité de brièveté. Le remplacer par un appariement
  d'attributs discrets, mode, créneau, motif, météo, comme le demande le ticket 051 § D.
- **Plongement : brancher le paramètre, garder un modèle anglophone.**
  ⚠ **Arbitrage rendu par l'auteur le 2026-09-14, conflit 071 / 074 tranché : le dispositif
  passe à 100 % anglais** — prompts, population, souvenirs. Le passage à un modèle francophone
  n'a donc plus d'objet : `Solon-embeddings-large-0.1` est **abandonné comme cible**, et avec lui
  l'argument « les souvenirs sont en français, le plongement est anglophone », qui fondait ce
  point. Ce qui reste à faire, et qui vaut indépendamment de la langue : brancher
  `embedding_model`, aujourd'hui **déclaré et relié à rien** — une seule occurrence dans
  `settings.py`, aucune lecture dans le code, le modèle étant codé en dur dans `llm/longterm.py`.
  Un paramètre qui ne commande rien est un mensonge de configuration, et il empêche de comparer
  deux modèles sans toucher au code. `all-MiniLM-L6-v2` est un modèle Sentence-Transformers
  (Reimers & Gurevych, 2019) entraîné sur un corpus anglophone d'après sa fiche, hérité de Vu et
  al. (2025, § 3.4.3) : **il redevient cohérent avec le corpus** une fois la bascule faite.
  Conséquence pour l'article : la référence MTEB-French (Ciancone et al., 2024) sort du § 3.3,
  et le rang de Solon n'a plus à être recoupé. Tout changement ultérieur de modèle imposerait une
  **reconstruction complète de l'index**, les vecteurs n'étant pas comparables d'un modèle à
  l'autre ; mesurable sur jeux gelés, sans run.

### Ancrage dans ACT-R, et ce qui en diverge

La relecture extérieure demande d'ancrer la somme pondérée dans l'équation d'activation d'ACT-R,
`A_i = B_i + Σ_j W_j S_ji + ε_i` (Anderson & Lebiere, 1998 ; Anderson et al., 2004). L'ancrage est
juste pour la **structure**, additive, et il est repris. Il est faux sur un point que la relecture
avançait et qu'il ne faut pas recopier : dans ACT-R, l'activation de base `B_i` encode la récence
et la fréquence des usages passés, `B_i = ln Σ_j t_j^(-d)`, et **pas** la valence ni la gravité
(Anderson & Schooler, 1991 ; Anderson & Lebiere, 1998). La gravité est une extension, sourcée
ailleurs (McGaugh, 2004). Le tableau dit, composante par composante, ce qui est repris et ce qui
diverge : c'est ce qui se transporte au chapitre 3 de l'article.

| Composante ici | Terme d'ACT-R | Source du terme | Divergence à dire |
|---|---|---|---|
| Poids temporel `exp(-Δt/force)`, depuis le dernier rappel | `B_i`, part récence et fréquence | Anderson & Schooler (1991) ; Anderson & Lebiere (1998) | ACT-R décroît en **loi de puissance** `t^(-d)` ; l'exponentielle vient de Park et al. (2023) et de MemoryBank (2024). Wixted & Ebbesen (1991) montrent que l'oubli humain suit une loi de puissance : l'exponentielle est une approximation assumée, pas un fait. |
| Gravité `I` (0,20) et sa modulation de `force` | **aucun** | McGaugh (2004) ; Park et al. (2023) pour l'importance au rappel | Extension hors ACT-R, non débrayable : le couplage est gardé en dur (§ 2.6). |
| Similarité sémantique (0,30) | `Σ_j W_j S_ji`, source `j` = texte de la situation | Anderson et al. (2004) ; Vu et al. (2025) pour le plongement | `S_ji` est ici un cosinus de plongements, non une force d'association apprise. |
| Affinité d'axes (0,20) | `Σ_j W_j S_ji`, sources `j` = mode, lieu, créneau, motif ; appariement partiel | Anderson & Lebiere (1998) | Bonus sans veto : même règle que la pénalité de discordance. |
| Affinité catégorielle (0,10, ex-« lexical ») | appariement partiel sur attributs discrets | Anderson & Lebiere (1998) ; ticket 051 § D | Remplace un terme sans fondement. |
| Bruit `ε_i` | `ε_i` | Anderson & Lebiere (1998) | **Non implémenté** : le rappel est déterministe pour que les ablations se rejouent ; la stochasticité vit dans la décision du modèle, à mesurer au ticket 068. |
| Confiance d'un concept (§ 2.5) | remplace `B_i` pour le registre sémantique | Tulving (1972) ; McClelland, McNaughton & O'Reilly (1995) | ACT-R applique la même activation de base à tout chunk ; la séparation des régimes est une divergence propre. |
| Top-K | seuil de rappel `τ`, un seul chunk | Anderson & Lebiere (1998) | ACT-R rend le chunk le plus actif au-dessus de `τ` ; le top-K est celui de Park et al. (2023). |

## 2.3 Lot 3 — consolider les concepts

**Fichiers** : `llm/longterm.py`, schéma et gabarit de `stm_reflection`.

- **Panier, pas identité.** Le couple objet-motif désigne un petit ensemble de candidats. Une
  identité unique par couple condamnerait l'agent à une seule pensée par mode et par motif,
  chaque concept nouveau détruisant le précédent. La présélection reste une correspondance exacte
  sur une métadonnée indexée : aucun balayage de l'index. Apport propre, qui corrige la faute
  relevée au ticket 051 § B.
- **Discrimination par désignation du modèle**, non par seuil. Les concepts du panier lui sont
  montrés dans l'appel qui a déjà lieu, il désigne celui qu'il met à jour ou déclare n'en mettre
  aucun. Coût marginal nul, aucun seuil arbitraire à calibrer. C'est le principe de Mem0
  (Chhikara et al., 2025) : le modèle choisit l'opération à appliquer aux souvenirs voisins qu'on
  lui montre. La voie par seuil de similarité, `cos > 0,85` proposée au ticket 051 § B sur le
  modèle d'A-MEM (Xu et al., 2025), est écartée : un seuil fixe sur un plongement francophone n'a
  pas de fondement mesuré.
- **Quatre opérations** : `creer`, `confirmer`, `preciser`, `contredire`, plus l'identifiant du
  concept visé. Champ `operation` au schéma de sortie. Correspondance avec Mem0 : `creer` = ADD,
  `preciser` = UPDATE, `confirmer` = NOOP plus un compteur, `contredire` remplace DELETE.
  **Il n'y a pas de suppression**, divergence propre : un concept dépassé est marqué et daté,
  parce que cette mise à l'écart est l'observable de l'hystérésis.
- **Confiance** par la règle de succession de Laplace (1814) : `(obs + 1) / (obs + contre_ex + 2)`.
  Sous un seuil, le concept cesse d'être servi **sans être supprimé** : sa mise à l'écart datée est
  la trace du changement d'habitude que l'expérience cherche à observer.
- **Les entrées épisodiques ne fusionnent jamais.** Seuls les concepts se consolident, faute de
  quoi l'agent se réduirait à un stéréotype sans vécu. C'est la séparation de Tulving (1972)
  entre épisodique et sémantique, et l'architecture à deux systèmes de McClelland, McNaughton &
  O'Reilly (1995) : les traces d'épisodes restent dans un magasin rapide, la régularité s'en
  extrait lentement dans un autre. Chez Vu et al. (2025, § 3.4), c'est la distinction entre
  *concepts* et *réflexions*.

## 2.4 Lot 4 — la mémoire noyau

**Fichiers** : `agents/llm_agent.py`, schéma et gabarit de `ltm_self_reflection`.

- Remplacer les dix souvenirs bruts par un **bloc permanent structuré**, complété de deux ou
  trois entrées épisodiques rappelées pour la décision en cours : « Mes habitudes », « Ce que je
  sais » avec le compteur d'observations par énoncé, « Ce qui a changé récemment ». Le principe
  est le *working context* de MemGPT (Packer et al., 2023, § 2.1) : un bloc toujours présent dans
  le contexte principal, le reste, *recall storage* et *archival storage*, étant paginé à la
  demande. Le terme « mémoire noyau » est celui de l'implémentation, pas de l'article.
- **Garde-fou** : le bloc des habitudes est produit par le **journal des trajets**, pas par le
  modèle. Divergence avec MemGPT, où le modèle réécrit lui-même son *working context* par appel
  de fonction : un bloc calculé depuis le journal reste vérifiable contre lui, un bloc réécrit
  par le modèle ne l'est plus. Seul le bloc de connaissances lui est confié.
- **Aucune métadonnée sur le bloc** : ni date de mise à jour, ni nombre de jours de vécu. Cela ne
  change aucune décision, coûte des jetons, et rompt la fiction que les gabarits maintiennent.
- L'entretien ne coûte rien de neuf : l'auto-réflexion longue durée tourne déjà tous les trois
  jours, seule la forme de sa sortie change. Rythme comparable à la réflexion hebdomadaire de
  GATSim (Liu et al., 2025), qui fait émerger des habitudes en simulation de transport.

## 2.5 Épisodique contre sémantique

Transversal aux lots 1 et 3, c'est le point le plus fort de l'expertise (ticket 051 § A).

```
score_temps(entrée)  = exp(-Δt / force)   si épisodique  (entrées brutes, réflexions)
score_temps(concept) = confiance          si sémantique  (concepts, résumés)
```

La distinction est celle de Tulving (1972) entre mémoire épisodique, des événements situés dans le
temps, et mémoire sémantique, des faits qui ne le sont pas ; Sumers et al. (2024) la reprennent
comme deux modules distincts du cadre CoALA pour les agents de langue. Que les deux registres
n'aient pas la même dynamique tient à l'architecture à deux systèmes de McClelland, McNaughton &
O'Reilly (1995) : le magasin sémantique se met à jour lentement, par accumulation d'observations,
et non à l'horloge. Qu'une ligne sature les jours de pluie ne devient pas faux parce que dix
jours ont passé. Sous le régime uniforme, ce concept tombe sous 3 % de son poids en dix jours,
`exp(-10/2,8) = 0,028`, et sort du top-K sans qu'aucune observation ne l'ait infirmé. La date de
dernière observation reste utilisée comme départage entre concepts de confiance égale, non comme
facteur d'effacement. Dans les termes d'ACT-R, la confiance remplace `B_i` pour le registre
sémantique : c'est une divergence propre, ACT-R appliquant la même activation de base à tous les
chunks (§ 2.2).

## 2.6 Deux arbitrages, rendus le 2026-09-14 sur avis extérieur

Les deux étaient ouverts. Une relecture extérieure les a tranchés ; ses avis sont retenus ici,
avec leurs sources. **État au 2026-09-14, après retour de l'auteur** : l'arbitrage 2 est
**confirmé** et reporté dans `memory-stm-ltm.md`, partie III ; l'arbitrage 1 est **suspendu** à
une question sur le critère de réfutation (ii) du chapitre 7, exposée à la fin de sa section.

### Arbitrage 1 — La gravité et la durée de vie : rendu le 2026-09-14, issue C

La gravité entrait par trois canaux ; le plancher est supprimé, il en reste deux, la constante de
temps et la composante propre. Le critère de réfutation (ii) du chapitre 7 suppose qu'allonger la
constante de temps déplace la courbe de reprise : tant que la constante de temps dépend elle-même
de la gravité, l'effet de l'oubli n'est pas séparable de celui de la distribution des chocs, et un
relecteur y verra une variable de confusion non contrôlée.

**Rendu de l'auteur, 2026-09-14 : issue C. Le critère (ii) et le bras `exp_04d` sont
supprimés ; `α` n'existe pas ; le couplage `force = S0 × (1 + k × I)` est gardé tel quel.**
Aucune ligne de code ne bouge : `α` n'avait jamais été implémenté. Ce qui bouge est
documentaire, et listé à la fin de cette section.

Le raisonnement qui y conduit, conservé parce qu'il devra être tenu devant un relecteur.

Une relecture extérieure proposait `force = S0 × (1 + α × k × I)`, `α ∈ {0, 1}`, avec `α = 1`
pour le modèle cognitif complet — la gravité allonge la rétention, ce que la mémoire
émotionnelle documente (McGaugh, 2004) — et `α = 0` réservé à un bras de sensibilité isolant
l'effet de la constante de temps de celui des chocs.

**L'ambition de l'article n'est pas celle que le critère (ii) suppose.** L'article montre que des agents dotés de mémoire se comportent autrement que des
agents sans mémoire et qu'un système à règles ; la mémoire est un élément du dispositif, pas son
sujet ; il ne cherche pas à prouver, en isolation, le rôle causal de l'oubli. Or le critère (ii),
« l'hypothèse tombe si diviser la vitesse d'oubli par trois ne déplace pas la courbe », fait
tomber H3 sur l'effet du seul paramètre d'oubli : c'est une preuve causale isolée, et c'est
exactement ce que `α` servait à rendre propre. **Sans cette ambition, `α` n'a pas de raison
d'être.** Le § 3.5 signalait la sur-déclaration ; l'issue C la lève à la source.

Le critère (ii) était de plus **fragile par construction** sous le modèle cognitif complet. À
`α = 1`, un souvenir `marquant` part à 11,2 jours ; sur un horizon de cinq jours il ne décroît
presque pas, et tripler `S0` ne le change guère. Le bras de sensibilité mesure alors surtout la
persistance des souvenirs banals, et la courbe de reprise peut ne pas bouger pour une raison qui
ne dit rien de l'hypothèse : le critère « réfuterait » H3 à tort.

| Poids temporel `exp(-Δt/force)` du choc, `Δt = 3` jours | `S0 = 2,8` | `S0 = 8,4`, soit ×3 |
|---|---|---|
| `α = 0`, `force = S0` | 0,34 | 0,70 |
| `α = 1`, `I = 1`, `force = 4 × S0` | 0,77 | 0,92 |

Dans la spécification cible, la reprise n'est d'ailleurs **pas** conçue comme portée par l'oubli
du choc : elle se gagne par les trajets réussis qui relèvent la confiance des concepts (lot 3) et
par la dilution du choc dans le top-K. Un critère qui exige que l'oubli déplace la courbe teste
un mécanisme que le dispositif n'a pas retenu.

**Trois issues étaient ouvertes ; l'auteur a retenu la C le 2026-09-14.**

- **A. Garder (ii) comme critère de réfutation**, avec `α = 0` et le bras témoin. Le plus fort
  pour un relecteur, mais il déclare une ambition causale que l'auteur n'a pas, et il coûte un
  paramètre, un bras et une réécriture du protocole. *Écartée.*
- **B. Reformuler (ii) en vérification de robustesse.** Le bras `exp_04d` reste mais rend compte
  au lieu de tester. *Écartée : elle garde un run pour une question que l'article ne pose pas.*
- **C. Supprimer (ii) et `exp_04d`. ✅ Retenue.** Économise un run. Laisse ouverte la question
  qu'un relecteur posera sur la sensibilité au paramètre d'oubli choisi — la réponse ne passe
  plus par un bras, mais par la **règle de conception** de chaque constante et son second point
  de sensibilité publié (§ 2.10) : `S0 = 2,8` j, hérité de Vu et al., contre `S0 = 8,3` j, la
  valeur de Park et al. C'est un argument de spécification, pas une mesure, et le dire ainsi
  vaut mieux que de laisser croire à une preuve causale.

La suppression est légitime : les tickets 041 et 063 sont « à faire », aucun run `exp_04*`
n'existe dans les archives, et un pré-enregistrement s'amende avant les données, daté et motivé.
Elle a touché, le 2026-09-14 : `PROTOCOLE_SCIENTIFIQUE.md` § 5.3, `experiments.yaml` (bloc
`exp_04d` supprimé), le README et le plan longitudinal du dossier `experience_plan/`, le ticket
063, le suivi des actions (tâche 40 supprimée) et les planches du séminaire, hors verrou ; le
chapitre 7 et les trois introductions FR/EN/Overleaf, sous accord explicite du même jour. Le
critère (ii) y est remplacé par la **non-monotonie de la reprise**, déjà annoncée comme
falsifieur dans l'introduction et jusque-là absente de la liste du chapitre 7 : la liste reste
à trois critères.

### Arbitrage 2 — Le plancher journalier est le régime, le déclenchement intrajournalier est l'exception : confirmé

Trois régimes étaient en balance : plancher journalier seul, réflexion par déplacement,
déclenchement par gravité cumulée. **Rendu : plancher journalier à 22 h, consolidé au ticket 048,
plus un déclenchement intrajournalier réservé aux ruptures, `I_cumul ≥ Θ`. La réflexion par
déplacement est abandonnée.** Confirmé par l'auteur le 2026-09-14, « réflexion de nuit sauf
gravité exceptionnelle », et reporté dans `memory-stm-ltm.md`, partie III, avec le paramètre
`memoire__theta_gravite_cumulee`, fixé à 0,7 le 2026-09-14 (§ 2.10).

Ce qui fonde ce rendu, et ce qui ne le fonde pas :

- **Plausibilité cognitive.** La consolidation mnésique humaine est favorisée par le sommeil et
  les périodes hors ligne (Diekelmann & Born, 2010) ; l'architecture à deux systèmes place
  l'extraction des régularités dans un rejeu différé, pas dans le temps réel de l'épisode
  (McClelland, McNaughton & O'Reilly, 1995). Vu et al. (2025, § 3.6) spécifient la réflexion à la
  fin de chaque jour simulé. Une réflexion par déplacement irait contre ces trois sources.
- **Coût.** La relecture extérieure annonçait un facteur 3 à 4 sur l'inférence. **Ce chiffre ne
  tient pas** devant la mesure du ticket 048 : 0,69 appel mémoire par déplacement aujourd'hui,
  0,69 à 0,96 avec le plancher, 1,05 par déplacement, soit +22 % sur la campagne et ×1,5 au plus
  sur la part mémoire. Le rendu ne change pas, mais il s'appuie sur le chiffre mesuré, pas sur
  celui de la relecture.
- **Variance.** La relecture invoquait une « explosion de la variance stochastique » en journée.
  Elle n'est pas mesurée : c'est l'objet du ticket 068, encore à faire. À ne pas écrire comme un
  fait.
- **Le seuil `Θ`.** Chez Park et al. (2023, § 4.2), le seuil cumulé se franchit deux ou trois fois
  par jour : c'est un régime courant. Ici il doit rester exceptionnel, donc `Θ` se règle sur la
  distribution mesurée de `I_det` par agent-jour, qu'aucun run exploitable ne donne aujourd'hui.
  **Le préalable de mesure du ticket 048 tient toujours**, pour régler `Θ` et non plus pour
  choisir le régime.

## 2.7 Reste au ticket 048

Brancher `memory_decay_lambda` et `memory_horizon_days` du fichier d'expériences, aujourd'hui lus
par **aucun code**, vérifié le 2026-09-14, seules occurrences dans `experiments.yaml` et le suivi
des tickets, sur la constante de temps en jours, `force = 1 / λ`. **Toujours à faire malgré
l'issue C** : plus aucun bras ne fait varier λ, mais `exp_04a` en déclare un (0,4) que le code
n'applique pas — un run qui ne respecte pas sa propre fiche. Aucun paramètre `α` à ajouter,
l'arbitrage 1 l'ayant abandonné. Et instruire la piste des modèles locaux pour les réflexions, sous condition de mesure sur
jeux gelés.

## 2.8 Ouvert, de moindre priorité

**Divergence métadonnées / index hors nettoyage.** Les entrées d'un format non relisible sont
ignorées au chargement et restent dans l'index. Fermer ce chemin demanderait de vérifier
l'appartenance de chaque document aux métadonnées actives à chaque rappel, sur le chemin critique.
Écarté comme disproportionné. **À rouvrir si un run montre des souvenirs servis absents des
métadonnées.**

## 2.9 Évalué, non retenu

**Le régime Système 1 / Système 2**, ticket 051 § C : automatisme machinal par défaut, modèle
réveillé sur rupture. L'auteur a tranché le 2026-09-11 et confirmé le 2026-09-14 en faveur de la
**mesure** de l'habitude. Coder l'habitude interdirait de montrer qu'elle émerge, et le reproche
que l'expertise adresse au dispositif, un modèle de fréquences habillé d'une couche de langage,
s'appliquerait alors à sa propre proposition. La voie retenue est de mesurer si l'entropie du
choix décroît sans qu'aucune ligne ne l'impose ; un court-circuit de routine deviendrait alors une
optimisation justifiée par une mesure.

**La diffusion sociale des souvenirs** au-delà du ménage. Le graphe serait un artefact
d'échantillonnage : 294 IRIS pour 1 000 agents, médiane de 3 agents par IRIS, 145 IRIS sur 294
n'en portant qu'un ou deux, et le champ `employment_sector` est un secteur d'activité, pas un
lieu de travail. Le résultat dépendrait d'une topologie non mesurée. **Le périmètre ménage, lui,
est fondé** : l'appartenance au ménage est une marge contrôlée de la cohorte scellée, et 69
ménages sur 499 comptent plus de conducteurs mobiles que de voitures, en comptant les membres
titulaires du permis et non immobiles, parmi les ménages qui ont au moins une voiture ; sans
cette restriction, 44 ménages sans voiture mais avec conducteur portent le compte à 113. Ces
chiffres sont recalculés le 2026-09-14 depuis
`data/population/population_1000_AAMAS_v5/population.json`. Il rejoint la négociation
intra-ménage, qui relève d'un ticket propre et non de celui-ci.

## 2.10 Les constantes, fixées le 2026-09-14 et publiées avec leurs règles

Décision de l'auteur : **on publie les chiffres.** Chaque constante porte une règle de conception
en une phrase, rattachée au phénomène et non à l'horizon ; le même jeu vaut pour cinq jours comme
pour soixante, l'horizon maximal visé. Ce qui rend une valeur défendable n'est pas une citation
mais la règle, la date, et un point de sensibilité. Le jeu complet est dans
[`memory-stm-ltm.md`](../arch/memory-stm-ltm.md), « Paramètres de la partie III ». Ce qui change
par rapport à la première version de la spécification :

| Constante | Avant | Maintenant | Pourquoi |
|---|---|---|---|
| `k`, allongement par la gravité | 3 | **6** | L'ancre du niveau `marquant`, « je m'en souviendrai dans un mois » : moitié du poids à deux semaines, un cinquième à trente jours. À 3, il tombait à 7 % en un mois. |
| Renforcement au rappel | `× 1,15` | **`+ 1 jour`** | Sur soixante jours, le facteur saturait tout ce qui est rappelé souvent en dix-sept rappels. |
| `FORCE_MAX` | 30 j, au renforcement | 30 j, **dès l'écriture** | Aucune durée de vie ne dépasse le plafond, même quand `S0` triple. |
| Purge des entrées épisodiques | seuils par type, en service | **poids < 1 %** | 13 jours pour un trajet banal, 90 pour un `marquant` : jamais dans un run. |
| Fenêtre d'âge au rappel | 30 j | **= horizon**, 60 au plus | Le défaut aurait coupé le second mois. |
| `Θ`, déclenchement en journée | à mesurer | **0,7**, le seuil du choc | La panne de la ligne A vaut 0,8 ; à 1,0 le choc étudié n'aurait pas déclenché. La mesure vérifie la rareté. |
| Concept non servi | « sous un seuil » | **confiance < 0,5** | Contredit plus souvent que confirmé, exactement, sous Laplace. |
| Concept dépassé | 3 contre-exemples | **3 et confiance < 0,5** | Ni trois contradictions contre vingt confirmations, ni une majorité sur deux observations. |
| Second point de sensibilité | `S0 × 3`, 7,7 j | **`S0 = 8,3` j, Park et al.** | Un point publié plutôt qu'un choix local ; le run est presque le même. |

`S0 = 2,8` jours ne change pas ; sa règle est qu'un trajet banal pèse moins de 10 % après une
semaine, et son origine est à dire : héritée de l'implémentation de Vu et al., **non publiée
dans leur article**. `RETARD_REF` attend encore sa règle, à rattacher à la distribution des
durées de déplacement de la cohorte, mesurable sans run. **Cette dette a quitté ce ticket le
2026-09-21 : elle est le lot F5 du [ticket 095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md).**
Raison du transfert : le 095 a retouché la forme de cette courbe le même jour (palier →
asymptote) et `RETARD_REF` en est l'ancre préservée ; la laisser ici, dans un critère déjà
coché, revenait à ne la confier à personne.

**Coût d'un horizon de soixante jours**, à chiffrer avant de le fixer : d'après les volumes du
ticket 048, douze fois un bras de cinq jours, décisions et mémoire comprises. Depuis l'issue C
du § 2.6, le second point de sensibilité de `S0` (2,8 j hérité de Vu et al. contre 8,3 j publiés
par Park et al.) n'est plus un bras de run : c'est l'argument de spécification qui répond, seul,
à la question de la sensibilité au paramètre d'oubli.

---

# 3. Volet ARTICLE

## 3.1 Énoncés faux aujourd'hui

Aucun n'est suivi ailleurs : vérifié dans `actions.md`, `suivi_actions_publication.md` et
`ameliorations.md`.

| Emplacement | Ce qui est écrit | Ce qui est vrai |
|---|---|---|
| `fr/03_architecture.md` § 3.4 | « Au-delà d'un seuil d'entrées, une réflexion est produite » | **deux** conditions depuis le ticket 048, la seconde restaurant ce que Vu et al. spécifient, une réflexion à la fin de chaque jour simulé |
| ✅ `fr/01_introduction.md`, `en/01_introduction.md` et `overleaf/01_introduction.tex` | « un registre de mémoire **court terme** au sens de Park et al. (2023), à décroissance de taux λ » | la décision ne lit **que** la mémoire longue ; et le paramètre est une **constante de temps en jours**, non un taux. **Corrigé le 2026-09-14**, sous accord explicite, dans le même diff que la suppression du critère (ii) |
| `fr/09_conclusion.md` | « hystérésis J+1 avec mémoire court-terme » | même confusion |
| `relecture/00_abstract.md` | « un tampon à court terme décroissant » | même confusion |

## 3.2 Ce qui deviendra faux quand le code changera

- § 3.4, « pondérés 0,4 / 0,3 / 0,3 » : deviendra cinq composantes.
- § 3.4, « La décroissance dans le temps est ce qui permet à un souvenir de peser moins qu'hier
  sans disparaître » : ne vaudra plus que pour le registre épisodique.
- § 3.4, « ne rend que les dix meilleures entrées » : deviendra la mémoire noyau plus deux ou
  trois épisodiques.
- Chapitre 7, la formule de $\mathcal{M}_t$ et le poids $w_m(t)$ ne correspondent à aucun code.
- § 3.4, quand Vu et al. seront cités : dire que leurs poids publiés sont 0,3 / 0,3 / 0,4, la
  récence portant le poids fort, et que l'inversion en service est propre au dépôt (§ 1).
- ✅ **Fait le 2026-09-14** — Chapitre 7, critère de réfutation (ii) : supprimé (§ 2.6, issue C)
  et remplacé par la non-monotonie de la reprise. Les mentions d'`exp_04d` et de λ ont quitté
  les trois introductions FR/EN/Overleaf ; `PROTOCOLE_SCIENTIFIQUE.md` § 5.3 et
  `experiments.yaml` suivent. Reste la formule de $\mathcal{M}_t$, ci-dessus, non tranchée.

## 3.3 Ce qui manque : la section 3.4 ne cite personne

Vérifié sur l'ensemble de `docs/paper/article/` : **aucune référence de mémoire n'y figure**, à
l'exception de Reflexion. Décrire une architecture qui est celle de Park et al. adaptée par Vu et
al., sans citer ni l'un ni l'autre, dans la section qui la décrit, est une faiblesse devant un
relecteur AAMAS.

Les notices ci-dessous ont été recoupées le 2026-09-14 sur la notice d'éditeur ou d'arXiv. Deux
notices avancées par la relecture extérieure étaient inexactes et sont corrigées : CoALA est paru
dans TMLR en février 2024, non à NeurIPS 2023 ; et l'équation d'activation d'ACT-R n'est pas dans
Anderson & Schooler (1991), qui établit ce que l'activation de base encode, mais dans Anderson &
Lebiere (1998) et Anderson et al. (2004).

| Référence | Notice recoupée | Où elle sert |
|---|---|---|
| Park, O'Brien, Cai, Morris, Liang & Bernstein (2023) | *Generative Agents: Interactive Simulacra of Human Behavior*, UIST '23, ACM, 1–22 ; arXiv:2304.03442 | § 3.4, filiation directe : importance, seuil cumulé, récence depuis le dernier rappel, top-K |
| Vu, Gaudou & Oberoi (2025) | *Modeling realistic human behavior using generative agents in a multimodal transport system*, arXiv:2510.19497 | § 3.4, l'adaptation dont ce dépôt est la suite ; poids publiés 0,3 / 0,3 / 0,4 ; réflexion en fin de journée |
| Anderson & Schooler (1991) | *Reflections of the environment in memory*, Psychological Science 2(6), 396–408 | ch. 8, ce que l'activation de base encode : récence et fréquence, en loi de puissance. **Pas** l'équation d'ACT-R |
| Anderson & Lebiere (1998) | *The Atomic Components of Thought*, Lawrence Erlbaum | § 3.4 et ch. 8, l'équation `A_i = B_i + Σ W_j S_ji + ε`, l'apprentissage de base, l'appariement partiel, le seuil de rappel |
| Anderson, Bothell, Byrne, Douglass, Lebiere & Qin (2004) | *An integrated theory of the mind*, Psychological Review 111(4), 1036–1060 | même équation, notice de référence pour un relecteur |
| Wixted & Ebbesen (1991) | *On the form of forgetting*, Psychological Science 2(6), 409–415 | ch. 8, l'oubli humain suit une loi de puissance : à citer là où l'exponentielle est assumée |
| Ebbinghaus (1885) | *Über das Gedächtnis*, Duncker & Humblot | § 3.4, la courbe d'oubli que MemoryBank reprend |
| McGaugh (2004) | *The amygdala modulates the consolidation of memories of emotionally arousing experiences*, Annual Review of Neuroscience 27, 1–28 | § 3.4 et ch. 7, la gravité allonge la rétention, régime `α = 1` |
| Diekelmann & Born (2010) | *The memory function of sleep*, Nature Reviews Neuroscience 11(2), 114–126 | § 3.4, la consolidation en fin de journée plutôt qu'en temps réel |
| McClelland, McNaughton & O'Reilly (1995) | *Why there are complementary learning systems in the hippocampus and neocortex*, Psychological Review 102(3), 419–457 | § 3.4 et ch. 8, deux systèmes : épisodique rapide, sémantique lent et différé |
| Tulving (1972) | *Episodic and semantic memory*, in Tulving & Donaldson (dir.), *Organization of Memory*, Academic Press, 381–403 | § 3.4 et ch. 8, la distinction épisodique / sémantique |
| Sumers, Yao, Narasimhan & Griffiths (2024) | *Cognitive Architectures for Language Agents*, TMLR, février 2024 ; arXiv:2309.02427 | § 3.4, la même distinction portée aux agents de langue (CoALA) |
| Zhong, Guo, Gao, Ye & Wang (2024) | *MemoryBank: Enhancing Large Language Models with Long-Term Memory*, AAAI-24, Proc. AAAI 38, 19724–19731 ; arXiv:2305.10250 | § 3.4, courbe d'oubli exponentielle et renforcement au rappel |
| Chhikara, Khant, Aryan, Singh & Yadav (2025) | *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory*, arXiv:2504.19413 | ch. 8, opérations ADD / UPDATE / DELETE / NOOP choisies par le modèle |
| Xu, Liang, Mei, Gao, Tan & Zhang (2025) | *A-MEM: Agentic Memory for LLM Agents*, NeurIPS 2025 ; arXiv:2502.12110 | ch. 8, évolution des notes à l'arrivée d'un souvenir ; voie par seuil écartée |
| Packer, Wooders, Lin, Fang, Patil, Stoica & Gonzalez (2023) | *MemGPT: Towards LLMs as Operating Systems*, arXiv:2310.08560 | ch. 8, le *working context* toujours en contexte, la mémoire noyau |
| Liu et al. (2025) | *GATSim*, arXiv:2506.23306 | § 3.4, réflexion périodique et formation d'habitudes en transport |
| Verplanken & Aarts (1999) | *Habit, attitude, and planned behaviour: is habit an empty construct or an interesting case of goal-directed automaticity?*, European Review of Social Psychology 10(1), 101–134 | ch. 8, l'habitude comme automatisme |
| Goodwin (1977) | *Habit and hysteresis in mode choice*, Urban Studies 14(1), 95–98 | ch. 7 et 8, l'hystérésis du choix modal |
| Gutiérrez, Shu, Gu, Yasunaga & Su (2024) | *HippoRAG*, NeurIPS 2024 ; arXiv:2405.14831 | ch. 8 **seulement**, comme piste. Aucun mécanisme n'en dérive : une filiation écrite sans lecture a été retirée le 2026-09-14 |
| Papineni, Roukos, Ward & Zhu (2002) | *BLEU: a method for automatic evaluation of machine translation*, ACL 2002, 311–318 | § 3.4, uniquement pour **ne pas** appeler BLEU ce qui n'en est pas un |
| Laplace (1814) | *Essai philosophique sur les probabilités*, Courcier | § 3.4, la règle de succession derrière la confiance |
| Reimers & Gurevych (2019) | *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks*, EMNLP-IJCNLP 2019 | § 3.4, le cadre dont `all-MiniLM-L6-v2` est un modèle |
| Ciancone et al. (2024) | *MTEB-French: Resources for French Sentence Embedding Evaluation and Analysis*, arXiv:2405.20468 | § 3.4, le classement où situer Solon ; rang à recouper |

## 3.4 Deux portes obligatoires

**Le PDF d'abord.** La règle de tenue de [`CITATIONS.md`](../paper/article/CITATIONS.md) exige
que le PDF soit dans `docs/paper/sources/etat_de_lart/`, ou que l'ouvrage soit consulté pour les
livres. **Aucune** de ces références n'y figure hors Park et al. (2023) et Vu et al. (2025),
vérifié le 2026-09-14 sur le contenu du dossier. Le dépôt est le préalable, et **il est porté
par ce ticket**, décision de l'auteur du 2026-09-14 : le ticket 065 n'a aucun thème mémoire dans
ses cinq thèmes et n'en reçoit pas. Le dépôt suit la règle de tenue de `CITATIONS.md`, les quatre
conditions à la main : PDF déposé ou ouvrage consulté, attribution exacte, passage identifié, clé
BibTeX. Il peut partir dès maintenant, sans attendre le code. La notice de CoALA que la relecture
extérieure donnait pour NeurIPS 2023 est recoupée : TMLR, février 2024. La même exigence vaut dans
les deux sens, et le tableau du § 3.3 dit pour chaque notice sur quoi elle est recoupée.

## 3.5 Signalement d'impact sur l'article, 2026-09-14

Rendu selon la skill `article-impact` à la clôture de la relecture. Il s'arrête au constat : toute
correction repasse par le verrou.

> ✅ **Le MAJEUR est traité le 2026-09-14**, sous accord explicite : l'issue C du § 2.6 supprime
> le critère (ii) à la source, dans le chapitre 7, les trois introductions, le protocole et
> `experiments.yaml`. **Le MINEUR reste ouvert** : la divergence de poids avec Vu et al. n'est
> toujours pas dite au § 3.4. Et la formule de $\mathcal{M}_t$ / $w_m(t)$ du chapitre 7, que le
> signalement visait au même endroit, **n'était pas dans le périmètre de l'issue C** : elle ne
> correspond toujours à aucun code et attend sa propre décision.

```
=== SIGNALEMENT ARTICLE ===
Aucun code ni protocole n'a changé ce jour : rien ne devient faux. Un risque de
sur-déclaration est signalé à la demande de l'auteur ; un énoncé devient incomplet.

MAJEUR — fr/07_untabulated_regimes.md l. 12-15 et l. 58 ; fr/01_introduction.md l. 70 ;
         en/01_introduction.md l. 70 ; docs/paper/methode/PROTOCOLE_SCIENTIFIQUE.md § 5.3
  A changé : l'auteur a clarifié le 2026-09-14 que l'article ne prétend pas isoler
  l'effet causal de l'oubli ; la mémoire est un élément du dispositif, pas son sujet.
  Sur-déclare : « L'hypothèse tombe si (ii) diviser la vitesse d'oubli λ par trois ne
  déplace pas la courbe » et « l'hypothèse tombe ... si λ n'a pas d'effet » font reposer
  H3 sur l'effet isolé du paramètre d'oubli ; la formule de M_t et de w_m(t) présente
  l'oubli comme le moteur de la reprise, alors qu'elle ne correspond à aucun code et que
  la reprise visée se gagne par la confiance des concepts. Le critère est en outre
  fragile sous le modèle complet : tableau du § 2.6.
  Action suggérée : reformuler (ii) en vérification de robustesse et rapporter le
  déplacement comme sensibilité (§ 2.6, issue B) ; remplacer la formule par la
  description du mécanisme réel. Protocole et experiments.yaml hors verrou ; chapitre 7
  et introductions sous verrou.

MINEUR — fr/03_architecture.md § 3.4 (l. 46)
  A changé : le ticket établit que les poids en service 0,4 / 0,3 / 0,3 inversent ceux
  publiés par Vu et al. (0,3 / 0,3 / 0,4, la récence portant le poids fort).
  Devient incomplet : « pondérés 0,4 / 0,3 / 0,3 » est vrai du code ; quand la section
  citera Vu et al., la divergence devra être dite.
  Action suggérée : une relative, « là où Vu et al. donnent le poids fort à la récence ».
  Pas d'équivalent en/03 : la version EN ne compte que le résumé, l'introduction et
  l'état de l'art.

Rien à signaler sur : fr/00_abstract, en/00_abstract, relecture/00_abstract (le
« tampon court terme » y est déjà au § 3.1 de ce ticket), fr/04, fr/05, fr/06, fr/08,
fr/09, fr/99, plan/PLAN.md (aucune mention des poids ni du critère (ii)).
```

**Le verrou ensuite.** Diff présenté, accord explicite, un seul accord par tâche.

---

# 4. Volet PLANCHES — `Divers/`

Deux jeux existent. Le générateur de l'un est versionné, l'autre non.

| Fichier | Contenu | État |
|---|---|---|
| `architecture_proposée.pptx` | 8 slides, la spécification cible | **à jour au 2026-09-14** |
| `memoire_agents_mobilite.pptx` | 5 slides, comparaison de l'actuel et du proposé | **périmé sur trois points, à porter à ~20 slides** |

## 4.1 `architecture_proposée.pptx` — à jour, et ce qui la fera bouger

Les révisions du 2026-09-14 y sont : le panier en slide 5, la distinction épisodique et
sémantique en slide 6 avec la courbe plate du concept jamais contredit, la suppression du
plancher. Ce qui devra changer ensuite, **selon les arbitrages du § 2.6** :

- arbitrage 1 rendu (issue C) : la slide 3 garde la force dépendante de la gravité et
  **n'affiche aucun paramètre `α`** ; la courbe de la slide 6 garde ses deux régimes, sans
  courbe d'ablation en pointillé ;
- si le terme lexical devient une affinité catégorielle, la slide 7 remplace « Lexical » dans
  l'histogramme des cinq composantes, et peut porter la correspondance ACT-R du § 2.2 ;
- arbitrage 2 rendu : la slide 4 dit « plancher journalier à 22 h, déclenchement intrajournalier
  sur `I_cumul ≥ Θ` réservé aux ruptures », une fois le lot 1 codé.

## 4.2 `memoire_agents_mobilite.pptx`

Ce jeu oppose le dispositif actuel au proposé. Trois de ses affirmations ont vieilli.

- La slide 2 présente « les concepts s'empilent sans jamais se corriger » et « le rappel ignore
  le contexte » comme des angles morts : ils restent vrais, mais la slide 5 doit dire que la
  correction passe par un **panier** et non par une identité.
- La slide 3 montre un plancher sous la courbe d'oubli : **le plancher est supprimé**.
- Aucune slide ne porte la distinction épisodique et sémantique, qui est devenue le point central.

**Aucun générateur n'existe pour ce jeu**, contrairement à l'autre. Le reconstruire ou le retirer
est un choix à faire : un jeu de planches sans générateur se périme en silence, comme celui-ci
vient de le démontrer.

Globalement détaille beaucoup plus le fonctionnement de la mémoire 20 slides

### ✅ Reconstruit le 2026-09-21 — et ce n'était pas trois affirmations, c'était l'axe

Le constat ci-dessus sous-estimait le problème. Ce jeu était bâti sur *« voilà ce qui cloche
aujourd'hui → voilà les briques qu'on va poser → voilà ce qu'on y gagnera »* : sa slide 2
vendait des angles morts, sa slide 5 opposait un « Aujourd'hui » à un futur. **Les cinq lots
étant livrés et le 077 ayant suivi, le proposé EST l'actuel** : on ne promet pas ce qui est
fait. Ce n'étaient donc pas trois slides à corriger mais l'histoire entière à refaire.

Nouvel axe, arbitré par l'auteur : **la vie d'un souvenir**, en vingt planches et cinq actes.
Un seul cas — trente minutes de retard un mardi à 17 h 10, ligne A interrompue — traverse tout
le deck, du trajet qui crée le souvenir à la décision du vendredi qu'il infléchit. Le deck
**décrit** un dispositif qui existe ; il ne plaide plus pour un dispositif à construire.

Générateur versionné : [`scripts/slides/memoire_agents_mobilite.js`](../../scripts/slides/memoire_agents_mobilite.js).
Les chiffres du deck sont réunis dans un objet `CAS` en tête du fichier et ont été relevés **en
exécutant** `llm/gravite.py` : gravité 0,70, durée de vie 14,56 j contre 2,80 j pour un trajet
banal, 81,4 % du poids restant à J+3. Trois débordements de texte ont été trouvés au rendu
(LibreOffice → PDF → PNG) et corrigés — le XML ne les montrait pas.

**Un écart relevé en écrivant la planche 4 :** la spécification cible annonçait « 15 champs
plus 3 sur les concepts ». Le code en porte **23** — 17 communs, 5 propres au concept, plus
`schema_version`. L'arbitrage du lot 2 (cinquième axe, météo) et le lot 3 ont creusé l'écart.
La planche dit le compte du code et signale celui de la spécification.

## 4.3 Comment mettre à jour

Le générateur du premier jeu est versionné dans
[`scripts/slides/architecture_memoire.js`](../../scripts/slides/architecture_memoire.js). **On
modifie le générateur, jamais le `.pptx`.** Node résout `pptxgenjs` depuis le répertoire courant,
donc la commande se lance depuis un dossier où le module est installé.

✅ **Les deux obstacles matériels sont levés le 2026-09-21.** `pptxgenjs` est installé
(`npm install pptxgenjs`, et `node_modules/` est entré au `.gitignore`, il n'y était pas). Le
fichier `~$architecture_proposée.pptx` a disparu : la présentation n'est plus ouverte.

**Le deck 1 n'avait pas besoin d'être régénéré.** L'hypothèse « le `.pptx` est en retard sur son
générateur », tirée des dates de fichiers, était fausse : le `22:32` du 14/09 que portent
`scripts/slides/` et `specs/ticket_071/` est un horodatage de masse, trace d'un `git checkout`,
pas d'une édition. Vérifié en régénérant et en diffant : **le XML des planches est identique**,
seuls l'horodatage de création et les classeurs Excel embarqués diffèrent. Le binaire n'a donc
pas été remplacé par un contenu identique.

**La charte est extraite** dans [`scripts/slides/_charte.js`](../../scripts/slides/_charte.js) :
palette, polices, gabarit et les quatre aides de tracé, partagés par les deux générateurs. Deux
générateurs qui redéclarent chacun leur palette divergent à la première retouche. L'extraction a
été validée par la même épreuve : deck 1 régénéré, XML identique. Le mode d'emploi et l'épreuve
sont dans [`scripts/slides/README.md`](../../scripts/slides/README.md).

**Défaut corrigé au passage :** les générateurs écrivaient dans le répertoire courant, ce qui
déposait un `.pptx` orphelin à la racine du dépôt dès qu'on les lançait d'ailleurs. Le défaut
est désormais `Divers/<nom>.pptx`.

---

# 5. Ordre d'exécution

| Rang | Quoi | Pourquoi dans cet ordre |
|---|---|---|
| 1 | ✅ **Fait le 2026-09-14.** Les deux arbitrages du § 2.6 sont rendus : (2) plancher journalier confirmé ; (1) issue C, critère (ii) et `exp_04d` supprimés, pas de `α`. Protocole et article amendés le même jour | ils changent ce qu'on code, pas seulement comment |
| 2 | Mesurer le taux d'entrées et la distribution de `I_det` par agent-jour sur un run GAMA | règle le seuil `Θ` du déclenchement intrajournalier, ticket 048 |
| 3 | Lot 1, la gravité | tous les autres lots s'y appuient |
| 4 | Lot 2, le plongement francophone et les trois viviers | mesurable sur jeux gelés, sans run |
| 5 | Lot 3, la consolidation des concepts | dépend de la gravité |
| 6 | Lot 4, la mémoire noyau | dépend des compteurs du lot 3 |
| 7 | Dépôt des PDF du § 3.3, porté par ce ticket | peut partir dès maintenant, indépendant du code |
| 8 | Article et planches | après que le code a cessé de bouger, et après le dépôt |

Les corrections d'énoncés faux du § 3.1 font exception : elles portent sur le dispositif **en
service** et peuvent partir dès qu'un accord est donné.

---

## Critères de clôture

- [x] L'arbitrage 2 du § 2.6 est confirmé par l'auteur le 2026-09-14 et écrit dans
      `memory-stm-ltm.md`, partie III, paramètre `Θ` compris.
- [x] Les constantes de la spécification cible sont fixées avec leurs règles et publiées, § 2.10
      et partie III de la spécification. **`RETARD_REF` faisait exception** : sa règle de conception
      n'était pas écrite, et elle était consignée ici même, à l'intérieur de cette case cochée —
      donc invisible. Elle est **sortie du 071 le 2026-09-21** et portée par le **lot F5 du
      ticket 095**, qui tient l'échelle de gravité depuis son passage palier → asymptote.
- [x] La question du § 2.6 sur le critère (ii) est tranchée le 2026-09-14 — **issue C**, le
      critère et le bras `exp_04d` sont supprimés. L'arbitrage 1 en découle : pas de paramètre
      `α`, couplage gardé tel quel, écrit dans `memory-stm-ltm.md`.
- [x] Le protocole est amendé avant tout run `exp_04*` : `PROTOCOLE_SCIENTIFIQUE.md` § 5.3,
      `experiments.yaml`, `experience_plan/README.md` et `ETAPE_3A_PLAN_LONGITUDINAL.md` hors
      verrou ; chapitre 7 et introductions FR/EN/Overleaf sous accord explicite du 2026-09-14.
- [x] **Les quatre lots sont implémentés et testés le 2026-09-14**, et la partie III est repliée
      dans la partie II lot par lot. 249 tests de mémoire, tous verts ; chaque lot a son contrat
      de test rédigé AVANT son code, dans `specs/ticket_071/`. Six défauts de la spécification
      cible y ont été trouvés et corrigés avant d'écrire une ligne.
- [ ] Les quatre énoncés faux du § 3.1 sont corrigés dans l'article, sous accord explicite.
      **1 sur 4 fait le 2026-09-14** (les introductions FR/EN/Overleaf) ; restent `fr/03` § 3.4,
      `fr/09_conclusion.md` et `relecture/00_abstract.md`.
- [ ] Les PDF des références du § 3.3 sont déposés dans `etat_de_lart/`, ou l'ouvrage consulté
      pour les livres, ou la citation est renoncée ; le dépôt est porté par ce ticket, et chaque
      notice passe les quatre conditions de `CITATIONS.md`.
      **Instruit le 2026-09-14** : [`docs/paper/sources/DEPOT_MEMOIRE_TICKET_071.md`](../paper/sources/DEPOT_MEMOIRE_TICKET_071.md)
      classe les 24 références en quatre groupes — 8 préprints arXiv et 2 actes en accès ouvert,
      **déposables tout de suite** ; 8 articles sous licence éditeur, à trancher entre accès
      institutionnel et mention « ouvrage consulté » ; 4 ouvrages sans PDF. Vérifié : **2 des 24
      sont dans `etat_de_lart/`**, Park (2023) et Vu (2025), et seules ces deux clés BibTeX
      existent. ⚠ Ciancone et al. (2024) **sort de la liste** : le passage au plongement
      francophone est abandonné, la référence n'a plus d'objet. Le dépôt lui-même reste à faire
      et demande une main humaine — ni un paywall ne se contourne, ni un ouvrage ne se consulte
      à ma place.
- [ ] Le signalement du § 3.5 est traité : les deux énoncés incomplets sont corrigés sous accord
      explicite, ou la décision de les laisser est écrite.
- [x] **Les deux jeux de planches reflètent l'état du code, le 2026-09-21.** Le second est
      reconstruit en **vingt planches** sur un axe neuf — *la vie d'un souvenir*, l'ancien axe
      « actuel contre proposé » étant devenu sans objet — avec son générateur versionné comme le
      premier, et une charte commune extraite. Le premier n'a pas eu à bouger : vérifié en
      régénérant et en diffant son XML, il portait déjà les révisions du 14/09. Les deux
      obstacles matériels du 2026-09-14 sont levés : `pptxgenjs` installé sous accord de
      l'auteur, `node_modules/` ajouté au `.gitignore`, et le fichier de verrou PowerPoint
      disparu. Mode d'emploi, épreuve de non-régression et vérification du rendu :
      `scripts/slides/README.md`.
