# Ticket 051 — Réflexion, audit épistémologique et refonte de l'architecture mémoire des agents

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 3 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Nature du ticket** : **Tâche d'analyse, d'arbitrage théorique et de cadrage conceptuel.** Ce ticket formalise une réflexion scientifique approfondie sur ce qu'est la mémoire d'un agent de mobilité (épisodique vs sémantique, formation d'habitudes, dynamique d'hystérésis). Il ne fige pas une solution définitive immédiate mais pose l'état des lieux, les verrous identifiés et la feuille de route pour le papier AAMAS et les développements futurs.

---

## 1. Contexte & Diagnostic Exécutif

L'architecture de mémoire court-terme (STM) et long-terme (LTM) de la plateforme (`docs/arch/memory-stm-ltm.md`) présente des réussites d'ingénierie logicielle remarquables (l'ordonnancement EDF asservi au réveil simulé, le drainage nocturne, le démontage mathématique de la normalisation min-max de Park et al. au Ticket 048, et les garde-fous sur chocs physiques).

Néanmoins, l'audit scientifique et épistémologique révèle plusieurs points de tension théoriques et méthodologiques majeurs face aux standards de la communauté cognitive et multi-agents (CoALA, ACT-R, benchmark SILICA, AAMAS) :
1. **Confusion entre mémoire épisodique et mémoire sémantique** : appliquer une décroissance temporelle d'oubli passive aux concepts généraux (ex. règles de saturation d'une ligne) est un contresens cognitif.
2. **Risque d'effondrement conceptuel par hachage rigide** : la réduction de l'identité des pensées à un hash `(mode, motif)` détruit la diversité des apprentissages d'un agent.
3. **Cadrage bibliographique rigoureux** : rectifier l'interprétation d'HippoRAG (diffusion d'activation PPR plutôt que restriction) et de la théorie de l'habitude (Système 1 automatique vs Système 2 délibératif).
4. **Assainissement mathématique du rappel** : éliminer les artefacts du pseudo « BLEU-2 » et le triple-compte de la gravité dans l'ancienneté.
5. **Vices cachés identifiés dans le code en production (`longterm.py`)** : synchronisation d'horloge (temps machine vs temps simulé GAMA), cohérence des suppressions ChromaDB et filtres temporels.

---

## 2. Synthèse de l'Expertise Épistémologique & Scientifique

### 2.1 Les acquis d'ingénierie validés (à préserver et valoriser)
* **Déboulonnage de la normalisation Min-Max de Park et al. (Ticket 048)** : Abandonner la renormalisation relative par lot au profit de valeurs absolues sur $[0, 1]$ avec constante d'oubli en jours calendaires réels ($S_0 = 2{,}8$ jours). Ce résultat restaure la comparabilité inter-décisions et doit être revendiqué comme une contribution propre.
* **Ordonnancement EDF nocturne** : Découplage complet de la délibération et de la réflexion via une file EDF calée sur l'échéance du réveil simulé (`next_wakeup_ts`), garantissant la mise à jour de la LTM avant le premier choix du matin sans bloquer la simulation diurne.
* **Échelle ordinale de gravité ancrée** : 5 échelons linguistiques (`anodin`, `notable`, `genant`, `grave`, `marquant`) réduisant la variance d'évaluation par rapport à une note 1-10 non ancrée.
* **Garde-fou physique déterministe** : $I_{\text{concept}} = \max(I_{\text{llm}}, \max(I_{\text{det}}))$, empêchant le nivellement optimiste du LLM face aux retards réels de GAMA.

---

### 2.2 Les verrous conceptuels à instruire

#### A. Le schisme Épisodique ($\mathcal{M}_{\text{epi}}$) vs Sémantique ($\mathcal{M}_{\text{sem}}$) — Cadre CoALA & Tulving
* *Le problème* : Actuellement, traces d'expériences (`CONVERSATION`/`EVENT`) et généralisations (`REFLECTION`/`CONCEPT`) partagent le même index et subissent la même érosion temporelle $\exp(-\Delta t / \text{force})$. Un concept général valide s'évapore ainsi après 10 jours sans que rien ne l'ait infirmé.
* *Axe de réflexion* : Séparer strictement :
  1. **Magasin Épisodique** : traces vécues horodatées en temps simulé, soumises à la décroissance d'Ebbinghaus / loi de puissance.
  2. **Magasin Sémantique** : croyances et règles stables, indépendantes du temps calendaire, mises à jour par inférence et confrontation d'observations (compteurs de confirmations vs contre-exemples / lissage bayésien de Laplace).

#### B. Résolution d'identité conceptuelle : du Hash cartésien au pattern A-MEM
* *Le problème* : La formule `identite = hash(axe_objet, axe_motif)` du Lot 3 force chaque agent à n'avoir qu'une seule assertion par couple (ex: `velo` / `travail`), provoquant l'écrasement mutuel de concepts portant sur le stationnement, l'itinéraire ou la météo.
* *Axe de réflexion* : Adopter le paradigme **A-MEM / Mem0** : plongement sémantique de l'assertion et calcul de similarité vectorielle ($\cos > 0{,}85$). Si collision sémantique, arbitrage (`confirmer`, `preciser`, `contredire`) ; sinon, création d'un nœud conceptuel distinct.

#### C. Cadrage théorique de l'habitude : Système 1 vs Système 2
* *Le problème* : Interroger ChromaDB et le LLM avec un prompt massif de 2 000 tokens à chaque déplacement nominal crée un agent hyper-délibératif et névrotique, tout en explosant les coûts d'inférence.
* *Axe de réflexion* : Poser la distinction fondamentale de Verplanken & Aarts (1999) : l'habitude est un automatisme machinal (Système 1). L'agent doit dérouler sa routine par défaut sans coût cognitif (coût token nul), et ne mobiliser la délibération sémantique LLM (Système 2) qu'en cas de **rupture de contexte / choc** (retard physique important, incident réseau, alerte météo).

#### D. Assainissement mathématique de la fonction de rappel (Retrieval)
* *Le problème* :
  - Le pseudo « BLEU-2 » n'est pas un score BLEU mais un rappel lexical asymétrique qui inflige une pénalité structurelle injustifiée de 30 % aux tags unigrammes (`tags = "métro"`).
  - Le « plancher temporel » $\phi \cdot I$ fige artificiellement le temps pour les événements marquants et produit un triple-compte de la gravité $I$ (dans la constante de temps, dans le plancher, et dans le poids direct).
* *Axe de réflexion* :
  - Remplacer le terme lexical par un indice d'affinité contextuelle catégorielle propre (Jaccard sur attributs discrets : motif, heure, mode, météo).
  - Supprimer le plancher temporel : la rémanence d'un choc est portée naturellement par l'allongement de sa constante de force et par le réservoir d'accès direct (Vivier de Chocs).

---

### 2.3 Anomalies techniques de code répertoriées (`longterm.py`)

1. **Désynchronisation d'horloge dans `cleanup_user_memories()`** :
   L'utilisation de `cutoff_date = datetime.now() - timedelta(...)` compare l'heure machine réelle de l'hôte aux timestamps simulés GAMA. Si le scénario tourne sur une date antérieure de plus de 30 jours, 100 % des entrées sont purgées au franchissement du seuil de 10 000 entrées.
2. **Orphelins dans l'index vectoriel ChromaDB** :
   La suppression dans les fichiers JSON locaux (`entries`) ne transmet pas de commande `collection.delete()` à ChromaDB. Les souvenirs fantômes restent indexés dans HNSW.
3. **Court-circuit du filtre de fenêtre glissante (`max_past_days`)** :
   Dans `filter_message`, le retour conditionnel direct sous `long_term_memory_filter_by_datetime` empêche l'évaluation de `max_past_days`, neutralisant le filtre temporel lorsque le filtre jour ouvré est actif.

---

## 3. Impacts sur la Rédaction de l'Article AAMAS

* **Chapitre 3 (section 3.4)** :
  - Présenter une vision conceptuelle épurée et robuste de la mémoire (couplage STM/LTM, distinction des traces et des réflexions).
  - Éviter d'affirmer des équations ou des analogies bibliographiques contestables (rectification de la mention d'HippoRAG, abandon du vocabulaire pseudo BLEU-2).
  - Cadrer honnêtement le statut de la mémoire actuelle : un dispositif expérimental d'accumulation d'expérience et d'érosion, préparant les perspectives cognitives.
* **Chapitre 7 (Régimes non tabulés — Étape 3a)** :
  - Documenter la cinétique d'hystérésis en qualifiant précisément le rôle de la persistance des souvenirs face à l'amnésie de l'oracle tabulaire.
* **Chapitre 8 (Limites et perspectives)** :
  - Valoriser l'évolution vers une architecture cognitive bi-niveau complète (Système 1 / Système 2) et un magasin sémantique explicite comme perspective majeure de recherche pour la simulation multi-agents.

---

## 4. Feuille de Route / Pistes d'Évolution

| Priorité | Horizon | Action |
|---|---|---|
| **P1 — Correctifs immédiats** | Court terme | Corriger les 3 anomalies dans `longterm.py` (horloge temps simulé GAMA, `collection.delete`, filtres). |
| **P2 — Assainissement Retrieval** | Court terme | Supprimer le plancher temporel et remplacer le pseudo BLEU-2 par l'affinité catégorielle. |
| **P3 — Rédaction Ch. 3 & 8** | Rédactionnel | Aligner la section 3.4 sur ces principes et formuler la prospective Système 1 / Système 2 en section 8. |
| **P4 — Évolution conceptuelle** | Moyen terme | Étudier la séparation physique des magasins épisodique et sémantique et la résolution par similarité vectorielle A-MEM. |

## Critères de clôture
- [ ] Le diagnostic théorique et les distinctions conceptuelles (épisodique vs sémantique, Système 1 vs 2) sont partagés et documentés.
- [ ] La section 3.4 de l'article est rédigée sans les biais ou contresens identifiés.
- [ ] Les correctifs de robustesse du code (`longterm.py`) sont ordonnancés.
