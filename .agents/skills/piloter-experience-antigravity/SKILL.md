---
name: piloter-experience-antigravity
description: >-
  Piloter ou rejouer une expérience de mobilité sans simulateur avec le décideur Antigravity
  (ex: Gemini 3.8 Flash, exp_agy-*), y compris avec substitution de modèle passée en paramètre
  (ex: /goal Rejoue exp_... mais avec <modele>). Utiliser ce skill dès que l'utilisateur demande de lancer,
  rejouer ou exécuter une expérience via Antigravity ou des sous-agents sans consommer de quota d'API.
---

# Piloter une Expérience avec le Décideur Antigravity

Ce skill guide l'agent pour orchestrer de bout en bout une expérience de mobilité en mode sans simulateur via le décideur `antigravity` (défini dans `specs/decideur-antigravity.md`).

Le décideur délègue chaque choix modal à des sous-agents via un protocole d'échange de fichiers IPC atomiques, sans appel réseau vers la passerelle ni consommation de quota externe.

---

## 1. Paramétrage du Modèle et Définition de l'Expérience

### 1.1 Analyse de la Commande et Extraction du Modèle
L'utilisateur peut demander d'exécuter une expérience en spécifiant explicitement un modèle cible différent de celui d'origine.

**Exemples de commandes supportées** :
- `/goal Rejoue exp_agy-gemini-31-f_minper_jtir_t0_nosim mais avec gemini 3.8 flash High`
- `/goal Rejoue exp_gemini-31-fl_minper_jtir_t0_nosim avec gemini-3.8-flash`
- `/goal Rejoue exp_agy-gemini-38-f_minper_jtir_t0_nosim` (conserve le modèle défini dans l'expérience)

**Résolution du modèle technique et de son slug canonique** :
Extraire le nom du modèle depuis la consigne et le faire correspondre à son identifiant technique et son slug canonique (règle N4 / `nommage.abreger_modele`) :

| Libellé Utilisateur | Modèle Technique (`decideur.modele`) | Slug Canonique (`slug`) | Préfixe Décideur |
|---|---|---|---|
| `gemini 3.8 flash` / `gemini 3.8 flash High` | `gemini-3.8-flash` | `gemini-38-f` | `agy-gemini-38-f` |
| `gemini 3.1 flash lite` / `gemini 3.1 flash` | `gemini-3.1-flash-lite` | `gemini-31-fl` | `agy-gemini-31-fl` |
| `gemini 3.5 flash lite` | `gemini-3.5-flash-lite` | `gemini-35-fl` | `agy-gemini-35-fl` |
| `mistral small` | `mistral-small-latest` | `mistral-s` | `agy-mistral-s` |
| Autre modèle | `abreger_modele(modele)` | `slug` | `agy-<slug>` |

### 1.2 Dérivation Canonique du Nom d'Expérience
Le nom suit la grammaire N2/N10 :
`exp_agy-<slug>_<prompt>_jtir_t<temp>_nosim`

En cas de substitution de modèle sur une expérience source :
- Remplacer le segment décideur par `agy-<slug>`.
- Conserver la variante de gabarit (`minper`, `expcha`, etc.), le tirage (`jtir`), la température (`t0`) et le mode (`nosim`).
- **Exemple** : `exp_agy-gemini-31-f_minper_jtir_t0_nosim` + `gemini 3.8 flash High`
  → `exp_agy-gemini-38-f_minper_jtir_t0_nosim`.

### 1.3 Fichier `experience.yaml`
1. Vérifier si `data/experiences/<NOM_EXP>/experience.yaml` existe déjà.
2. Si le fichier n'existe pas, le **créer automatiquement** en clonant la configuration de l'expérience source (`<EXP_SOURCE>`), en ajustant :
   - `nom`: `<NOM_EXP>` (ex: `exp_agy-gemini-38-f_minper_jtir_t0_nosim`)
   - `decideur.type`: `antigravity`
   - `decideur.modele`: `<MODELE_TECHNIQUE>` (ex: `gemini-3.8-flash`)
   - `derive_de`: `<EXP_SOURCE>` (ex: `exp_agy-gemini-31-f_minper_jtir_t0_nosim` ou `exp_gemini-31-fl_minper_jtir_t0_nosim`)

```yaml
nom: exp_agy-gemini-38-f_minper_jtir_t0_nosim
population:
  chemin: /data/eqasim-output/population_1000_AAMAS
jeu:
  nom: population_1000_AAMAS_20260316
  dossier: null
gabarit:
  categorie: itinary_multi_agent
  variante: prompt_minimal
decideur:
  type: antigravity
  modele: gemini-3.8-flash
  parametres:
    temperature: 0.0
    top_p: 1.0
    max_tokens: 4096
  rejeu_de: null
  graine: null
  artefact: null
mode: sans_simulateur
calendrier:
  politique: aleatoire
  date: '2026-03-16'
  graine: 42
horizon_jours: 1
memoire: false
evenements: []
graine_ordre: 42
graine_tirage: 42
regroupement:
  parallelisme: 8
tolerances_horaires:
  bike: insensible
  car: heure
  rail:
    pas_min: 10
  transit:
    pas_min: 10
  walk: insensible
max_candidats: 6
attente_max_s: 120
derive_de: exp_agy-gemini-31-f_minper_jtir_t0_nosim
```

---

## 2. Lancement du Runner en Arrière-Plan

Démarrer le processus runner dans un terminal (via `run_command` en tâche de fond) :

```bash
PYTHONPATH=llm-agents:mobility_llm/src:llm_gateway/src ./llm-agents/.venv/bin/python -m experiences.cli lancer <NOM_EXP>
```

Le runner initialise l'exécution dans `data/experiences/<NOM_EXP>/executions/<TIMESTAMP>/` et prépare le sous-dossier d'échanges IPC :
- `echanges/demandes/` : les requêtes écrites par le runner pour chaque décision à prendre.
- `echanges/reponses/` : là où l'agent doit déposer ses réponses.
- `echanges/demandes/traitees/` : où le runner déplace les demandes après consommation.

---

## 3. Boucle d'Orchestration IPC

L'agent pilote doit surveiller `echanges/demandes/*.json`.

### 3.1 Lecture de la Demande
Chaque fichier `echanges/demandes/<person_id>__<activity_id>.json` contient :
```json
{
  "version": 1,
  "person_id": "101",
  "activity_id": "act1",
  "modele_attendu": "gemini-3.8-flash",
  "n_options": 3,
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "schema_sortie": { ... }
}
```

### 3.2 Décision par Sous-Agent
Pour chaque demande :
1. Extraire les `messages`, le `modele_attendu` et le `schema_sortie`.
2. Invoquer un sous-agent (ou traiter directement dans la session si le modèle actif correspond à `modele_attendu`) en lui soumettant le prompt exact *verbatim*, sans ajout de consigne ni préambule.
3. Le sous-agent doit renvoyer la sélection conforme au schéma :
```json
{
  "agents": [
    {
      "agent_id": "<person_id>",
      "probabilities": [
        {"index": 0, "mode": "car", "probability": 80},
        {"index": 1, "mode": "pt", "probability": 20}
      ]
    }
  ]
}
```

### 3.3 Écriture Atomique de la Réponse
Déposer la réponse dans `echanges/reponses/<person_id>__<activity_id>.json` :
1. Écrire dans un fichier temporaire `<person_id>__<activity_id>.json.tmp`.
2. Renommer atomiquement vers `<person_id>__<activity_id>.json`.

Format strict de la réponse déposée :
```json
{
  "person_id": "<person_id>",
  "activity_id": "<activity_id>",
  "modele_declare": "<modele_attendu>",
  "agents": [ ... ]
}
```

> [!IMPORTANT]
> - `modele_declare` doit correspondre exactement au `modele_attendu`.
> - `person_id` et `activity_id` doivent correspondre exactement au fichier de demande.
> - Si le délai dépasse `attente_max_s / 4` (30s par défaut), le runner bascule en état `en_attente_agent` pour avertir du ralentissement, puis revient en `en_cours` dès réception.

---

## 4. Clôture et Validation

Une fois la simulation de la journée terminée :

1. **Vérifier l'intégrité de l'archive** :
   ```bash
   PYTHONPATH=llm-agents:mobility_llm/src:llm_gateway/src ./llm-agents/.venv/bin/python -c "
   from pathlib import Path
   from experiences.archive import valider_archive
   exec_dir = sorted(Path('data/experiences/<NOM_EXP>/executions').glob('20*'))[-1]
   erreurs = valider_archive(exec_dir)
   print('Erreurs archive:', erreurs)
   assert not erreurs
   "
   ```

2. **Comparer avec l'expérience source ou de référence** :
   ```bash
   # Comparer B (nouvelle exécution) avec A (exécution de référence de l'expérience source dans derive_de)
   make comparer \
     A=data/experiences/<EXP_SOURCE>/executions/<DERNIER_TIMESTAMP> \
     B=data/experiences/<NOM_EXP>/executions/<TIMESTAMP>
   ```

3. **Rédiger le rapport de fin de run** :
   - Nombre de déplacements décidés.
   - Répartition modale (voiture, TC, marche, vélo).
   - Taux de replis uniformes D10.
   - Présence du tag `modele_verifie: false` dans `execution.yaml` et `decisions.jsonl`.


---

## Sortie littérale du modèle (P8, obligatoire depuis le 2026-09-10)

Chaque fichier de réponse doit porter un champ **`sortie_litterale`** : le texte rendu par le
sous-agent **tel qu'il l'a émis**, sans retouche.

```json
{
  "version": 1,
  "person_id": "1234", "activity_id": "a7",
  "modele_declare": "gemini-3.8-flash",
  "sortie_litterale": "```json\n{\"agents\": [...]}\n```",
  "reponse_brute": "{\"agents\": [...]}",
  "agents": [{"agent_id": "1234", "probabilities": [...]}]
}
```

**Pourquoi ce champ existe.** L'audit du 2026-09-10 a constaté que les 2 287 `reponse_brute` du
run `exp_agy-gemini-38-f` étaient du JSON nu, sans une balise markdown ni une ligne de prose,
sous deux formes structurelles différentes selon le segment. Autrement dit une
re-sérialisation : aucune pièce de l'archive ne montrait ce que le modèle avait réellement
écrit. Or c'est la seule chose qui pourrait un jour étayer la vérification du modèle (P3 de
`specs/decideur-antigravity.md`).

**Règle d'usage.** `sortie_litterale` se recopie, ne se reformate pas — balises markdown,
préambule, espaces et retours à la ligne compris. Si tu ne peux pas la fournir, **omets le
champ** : le décideur inscrira `null` et comptera la réponse. Ne le remplis jamais avec une
version reconstruite : un trou déclaré est exploitable, une fausse pièce ne l'est pas.
