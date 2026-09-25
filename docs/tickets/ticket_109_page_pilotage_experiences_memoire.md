# Ticket 109 — Page de pilotage des expériences mémoire (choc, presse, multi-modèles)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-24, à la demande de l'auteur, dans la continuité des tickets
> [100](ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md) (canal d'événement unifié),
> [095](ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md) (routage par catégorie / enquêtes),
> [077](ticket_077_stabilisation_rejeu_long_terme_et_memoire.md) (rejeu multi-jours et mémoire),
> [106](ticket_106_le_souvenir_injecte_doit_atteindre_la_memoire_longue.md) (témoin mémoire longue) et
> [108](ticket_108_une_injection_declaree_qui_ne_se_produit_pas_doit_se_voir.md) (rapprochement des injections).
>
> **Objet.** L'onglet classique « 🧪 Expériences » du tableau de bord (`scripts/dashboard/experiences.py`)
> a été conçu pour composer et évaluer des expériences de choix modal sur 1 jour (métriques EMD, L1,
> comparabilité sur substrat de jeux scellés). Les expériences mémoire (chapitre 7 de l'article, ticket 100)
> opèrent sur un régime fondamentalement différent : horizon multi-jours, injection d'événements (chocs
> subis sur trajet ou articles de presse lus au réveil), orchestration contrefactuelle obligatoire (bras
> traité + bras témoin apparié consécutifs), et surtout **multiplicité des fonctions cognitives**
> sollicitant des LLMs (choix d'itinéraire, jugement de l'événement, consolidation du soir STM,
> auto-réflexion LTM, enquêtes).
> Ce ticket dote le tableau de bord de pilotage d'un **volet dédié aux expériences mémoire**, permettant
> de paramétrer, nommer canoniquement, lancer les deux bras et dépouiller ces campagnes avec leurs données.

---

## 0. Ce que ce ticket apporte à la plateforme et à la recherche

Aujourd'hui, lancer une expérience de mémoire nécessite d'éditer manuellement des scripts bash ou
d'appeler en ligne de commande `scripts/experiment/run_sequential_cohort.py` avec des variables
d'environnement (`MEMOIRE__*`, `EVENEMENT=`, `INSTANCES_ADMISES=`).
Les risques sont connus et documentés dans les tickets 077, 095, 100 et 108 :
1. Risque d'erreur de déclaration entre le choc/article et la population ciblée.
2. Impossibilité visuelle d'affecter un modèle différent par tâche cognitive (ex. un modèle rapide et
   robuste pour le choix d'itinéraire, un modèle à fort raisonnement pour la consolidation nocturne ou
   le jugement à l'injection).
3. Dispersion des données d'exécution entre `experiments/archive/` et `data/experiences/`.

Ce ticket apporte une **interface graphique de premier ordre** dans le tableau de bord Streamlit,
alignée sur les standards de rigueur du projet.

---

## 1. L'idée en une phrase

Un nouvel onglet de premier niveau **« 🧠 Expériences Mémoire »** dans le tableau de bord Streamlit
permettant de sélectionner un événement du catalogue (choc ou presse), de router les 5 fonctions
cognitives vers leurs modèles respectifs (avec mémorisation de l'expérience précédente), de paramétrer
la cohorte et l'horizon, puis d'exécuter consécutivement les bras traité et témoin sous un nom
canonique calculé avec archivage complet des données.

---

## 2. Décisions de l'auteur (2026-09-24)

| # | Question posée | Décision de l'auteur | Ce qu'elle engage |
|---|---|---|---|
| **D1** | Emplacement dans l'interface Streamlit | **Nouvel onglet de 1er niveau** `🧠 Expériences Mémoire` (slug `memoire`) | Séparation nette avec le choix modal 1 jour sans mémoire (`🧪 Expériences`), préserve la réactivité et la clarté du dashboard. |
| **D2** | Modèles par fonction cognitive | **Les 5 fonctions exposées**, valeur par défaut = celle de l'expérience précédente | Les 5 fonctions (`itinary_multi_agent`, `evenement_jugement`, `stm_reflection`, `ltm_self_reflection`, `enquete_affinite`) sont configurables individuellement. Un fichier de cache de formulaire persiste les derniers choix. |
| **D3** | Moteur d'exécution & contrefactuel | **Orchestration contrefactuelle A/B consécutive** ; l'expérience est terminée si les deux ont tourné | Le lancement enchaîne automatiquement la branche A (traitée, avec événement) et la branche B (témoin apparié, sans événement). L'état global ne passe à `terminée` que si les deux bras réussissent. |
| **D4** | Identité et numérotation | **Nom canonique calculé depuis les paramètres** | Application de la règle N1 (pas de saisie libre) : nom calculé selon le format `exp_mem_<canal>_<evenement>_<modele_decision>_<pop>_<horizon>j` avec gestion des collisions. |
| **D5** | Événement injecté | **Sélection stricte sur le catalogue existant** | L'utilisateur choisit parmi les déclarations validées de `config/evenements/` (`c1..c6`, `a07..a25`). Pas d'édition en ligne pour garantir l'intégrité des déclarations. |

---

## 3. Spécification fonctionnelle de la page

L'interface se structure en quatre panneaux :

### 3.1 Registre des expériences mémoire existantes
- Tableau des expériences mémoire exécutées ou en cours :
  - Colonnes : Nom canonique, Canal (`vecu` / `lu`), Événement injecté, Modèle Décision, Modèle Jugement, Modèle Réflexion, Population, Horizon, État global (`en_cours`, `traite_ok`, `terminee`, `echec`), Statut témoin mémoire (Ticket 106), Injections déclarées vs produites (Ticket 108).
- Actions : **Détail & Métriques**, **Reprendre (si arrêt)**, **S'inspirer de (recopie dans le formulaire)**, **Arrêter**.

### 3.2 Formulaire de composition : « Nouvelle expérience mémoire »

#### A. Canal et Événement injecté (Ticket 100 & D5)
- **Type de canal** : Sélecteur radio `⚡ Choc vécu (canal vecu, prise arrivée)` vs `📰 Article de presse (canal lu, prise reveil)`.
- **Événement du catalogue** :
  - Filtrage dynamique selon le canal choisi sur `services/llm-agents/config/evenements/*.yaml` :
    - Si `vecu` : `c1_bouchon_rocade`, `c2_crevaison`, `c3_panne_reseau`, `c4_train_supprime`, `c5_orage_grele`, `c6_voiture_suspecte`...
    - Si `lu` : `a07_greve_eboueurs`, `a09_vent_autan`, `a13_punaises_metro`, `a18_la_machine`, `a25_velotoulouse`...
  - Visualisation en lecture seule de la fiche de l'événement (description, jours d'injection ou fenêtre tirée, agents/foyers cibles, effet physique).

#### B. Modèles par fonction cognitive (D2 & Ticket 095 Lot C)
Chaque fonction propose un sélecteur de modèle issu de `providers.yaml` (ou LM Studio local), avec indication des quotas restants :
1. **Sélection d'itinéraire / Choix modal** (`itinary_multi_agent`) :
   - Modèle, température, budget de réflexion, variante de prompt (`prompts.yaml`).
2. **Jugement de l'événement à l'injection** (`evenement_jugement`, Ticket 100 D4/D7) :
   - Modèle estimant sévérité et valence à l'entrée du souvenir.
   - Option d'ablation : `jugement: aucun` (la gravité vaut le retard physique brut).
3. **Consolidation mémoire court terme / Soir** (`stm_reflection`) :
   - Modèle de réflexion nocturne et de production des croyances / récit du soir (Ticket 100 Lot 4).
   - Seuil minimal d'entrées (`stm_reflection_min_entries`, défaut 5).
4. **Auto-réflexion long terme** (`ltm_self_reflection`) :
   - Modèle périodique de consolidation LTM.
5. **Enquêtes de perception / Affinité** (`enquete_affinite`, Ticket 095) :
   - Modèle répondant aux questionnaires d'affinité quotidiens.

*Persistance (D2)* : À chaque enregistrement ou lancement, les choix des 5 modèles sont sauvés dans `.dashboard/formulaire_memoire.yaml` pour pré-remplir l'expérience suivante.

#### C. Population et Calendrier
- **Population** :
  - Cohorte de personas (ex. les 10 personas scellés du ticket 077/095, ou sélection unitaire : `861500`, `899549` Corinne, etc.).
  - Ou population de ménages/foyers scellée (ex. `population_20_foyers_059` pour la presse, `population_1000_AAMAS_v6`).
- **Calendrier & Horizon** :
  - Horizon en jours simulés (ex. 14, 30, 42 jours).
  - Politique : commune ou par foyer.
  - Option d'arrêt anticipé sur extinction du souvenir (`arret_sur_extinction.py`).

### 3.3 Nom canonique calculé (D4)
- Affiché dynamiquement dans un bandeau en tête de formulaire :
  `exp_mem_<canal>_<evenement>_<modele_decision>_<pop>_<horizon>j` (suffixé d'un indice en cas de collision).

### 3.4 Orchestration A/B et Données (D3)
- Le bouton **▶ Lancer l'expérience mémoire** arme un job d'orchestration qui :
  1. Lance le **Bras A (Traité)** : avec l'événement injecté, trace dans `data/experiences_memoire/<nom>/traite/`.
  2. Lance consécutivement le **Bras B (Témoin)** : conditions strictement identiques, sans événement (`EVT=0`), trace dans `data/experiences_memoire/<nom>/temoin/`.
  3. Effectue le rapprochement déclaré/produit (Ticket 108) et vérifie la présence du témoin en mémoire longue (Ticket 106).
  4. Marque l'expérience globale comme `terminee` une fois les deux bras validés.

---

## 4. Architecture technique

### 4.1 Fichiers impactés et créés

| Fichier | Nature | Description |
|---|---|---|
| `scripts/dashboard/memoire.py` | **Neuf** | Vue Streamlit de l'onglet « 🧠 Expériences Mémoire ». |
| `scripts/dashboard/app.py` | **Modifié** | Enregistrement de l'onglet `memoire` dans `ONGLETS` avec chargement paresseux (`lazy`). |
| `services/llm-agents/experiences/memoire.py` | **Neuf** | Modèle Pydantic `ExperienceMemoireConfig`, validation, persistance et calcul du nom canonique. |
| `scripts/experiment/orchestrateur_memoire.py` | **Neuf** | Exécuteur consécutif des deux bras (traité + témoin), encapsulant `run_sequential_cohort.py` et le stockage des données. |
| `make/memoire.mk` | **Neuf** | Cibles Makefile : `make memoire-lancer EXP=...`, `make memoire-estimer EXP=...`. |
| `scripts/dashboard/tickets_status.yaml` | **Modifié** | Statut et suivi du ticket 109. |

### 4.2 Injection de la table de routage multi-modèles
L'orchestrateur traduit les 5 choix de modèles en table `instances_admises` injectée via l'environnement au contrôleur et à la passerelle LLM :
```yaml
instances_admises:
  itinary_multi_agent: ["<instances_modele_1>"]
  evenement_jugement: ["<instances_modele_2>"]
  stm_reflection: ["<instances_modele_3>"]
  ltm_self_reflection: ["<instances_modele_4>"]
  enquete_affinite: ["<instances_modele_5>"]
  defaut: ["<instances_modele_1>"]
```

---

## 5. Lots de mise en œuvre

- **Lot 1 — Schéma & Modèle de données** : Modèle `ExperienceMemoireConfig`, sérialisation YAML, nommage canonique et persistance du formulaire (`.dashboard/formulaire_memoire.yaml`).
- **Lot 2 — Orchestrateur consécutif A/B** : `scripts/experiment/orchestrateur_memoire.py` et cible `make memoire-lancer`, assurant l'exécution séquentielle des deux bras et l'archivage étanche dans `data/experiences_memoire/<nom>/`.
- **Lot 3 — Interface Streamlit (`scripts/dashboard/memoire.py`)** : Rendu des 4 panneaux, sélecteur choc/presse sur catalogue, 5 sélecteurs de modèles avec quotas, bouton Lancer relié au registre de jobs.
- **Lot 4 — Dépouillement, témoins et rapprochement** : Intégration du témoin Ticket 106 et du contrôle d'injection Ticket 108 dans le panneau de suivi d'exécution.
- **Lot 5 — Tests et recette** : Tests unitaires pytest, test d'intégration à blanc (`DRY_RUN=1`) et documentation utilisateur.

---

## 6. Critères d'acceptation

- [x] L'onglet `🧠 Expériences Mémoire` est présent au 1er niveau dans Streamlit (`make dashboard`).
- [x] Le choix entre Choc et Presse filtre fidèlement le catalogue des événements de `config/evenements/`.
- [x] Les 5 fonctions cognitives disposent de leur sélecteur de modèle dédié, pré-rempli avec les choix de la session précédente.
- [x] Le nom canonique est calculé en temps réel sans possibilité de saisie libre.
- [x] Le lancement enchaîne automatiquement le bras traité puis le bras témoin consécutif, sans intervention manuelle.
- [x] L'expérience n'est déclarée `terminee` que si les deux bras ont terminé sans erreur.
- [x] Les données des deux bras sont archivées de manière étanche sous `data/experiences_memoire/<nom>/{traite,temoin}/`.
- [x] Les tests de régression existants et nouveaux passent à 100 %.
