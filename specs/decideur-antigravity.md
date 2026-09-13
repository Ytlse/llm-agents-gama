# Décideur `antigravity` — plan d'implémentation (v2)

Rejouer une expérience du mode sans simulateur en déléguant chaque décision à un sous-agent
Antigravity, sans consommer de quota d'API, **sans dégrader aucune garantie du ticket 035**.

Version 2 : réécriture après relecture du code. Les écarts de la v1 sont listés en annexe A.

---

## 1. Ce que ce canal produit — et ce qu'il ne produit pas

Le modèle qui sert un sous-agent Antigravity est choisi par le runtime de l'IDE. Aucun canal
ne renvoie son identité : là où `DecideurPasserelle` compare le `provider_used` rendu par la
passerelle à `allowed_providers` et refuse la substitution (`llm_agent.py:711/722`, Q2/Q3),
Antigravity n'offre rien d'équivalent. Le modèle est donc **déclaré, jamais vérifié**.

Conséquences, posées avant toute ligne de code :

- **P1** — Une exécution `antigravity` porte `modele_verifie: false`. Le drapeau vit dans
  l'empreinte décideur (`execution.yaml`) et dans chaque trace de `decisions.jsonl`.
- **P2** — Une exécution `modele_verifie: false` **ne fournit aucune mesure de parts modales**
  publiable, et ne sert pas de référence dans le plan d'expériences. Elle vaut pour ce qu'elle
  est : banc de mise au point de la mécanique, et mesure de coût nul.
- **P3** — La vérification du modèle est un **contrôle manuel de l'auteur** (décision du
  2026-09-09) : il s'assure hors du code que le sous-agent est bien servi par le modèle déclaré.
  Aucune machinerie n'est ajoutée pour l'imiter — `modele_verifie: false` dit seulement que la
  garantie ne vient pas du code. Si un canal de vérification apparaît côté Antigravity, il
  alimente le même champ et le drapeau bascule à `true`.

Cette version ne cherche donc pas à retrouver un résultat connu (cf. §8) : elle vérifie que la
mécanique produit une archive valide, complète et honnête sur ce qu'elle est.

---

## 2. Ce qui existe et n'est pas à réécrire

Le lotissement, l'ordonnancement et le respect de S4/D4 sont **déjà faits**, et le décideur n'a
rien à en connaître :

| Garantie | Où elle est tenue |
|---|---|
| Une coroutine par personne, `parallelisme` simultanées (8 par défaut) | `runner.py:523` (`asyncio.Semaphore`) |
| Déplacements d'une personne dans l'ordre horaire, jamais deux en parallèle (D4/S4) | `runner.py:570` (`traiter_personne`) |
| `avancer_chaine()` après chaque décision validée | `runner.py:584` et `runner.py:736` |
| Filtre `eligibilite()` → `plafonner()` → `ordre_presentation()` avant sollicitation | `decision.py:6` |
| 0 option → `sans_solution` · 1 option → `choix_unique`, décideur non sollicité | `decision.decider` |
| Reprise au déplacement près (S9), états, interruptions consignées | `runner.py` + spec 05 |
| Régime de regroupement enregistré (S5) | `execution.mettre_a_jour_regime` |
| Tolérance sur le vecteur de probabilités, repli uniforme tracé (D10) | `mode_choice.normalize_option_probabilities` |
| Rendu du texte effectivement présenté au modèle | `llm_gateway.prompts.engine.PromptEngine.render` |
| Comparabilité de deux exécutions par empreintes partagées (RG-4) | `registre.comparer` / `CHAMPS_PARTAGES` |

Aujourd'hui `unite_sollicitation = "deplacement"` : **une sollicitation = un déplacement**. Il
n'existe aucun lot inter-personnes, et `parallelisme = 8` n'est pas une taille de lot. Sur
l'exécution de référence, 1 034 sollicitations pour 2 637 décisions s'expliquent par la reprise
(`resservies: 1548`), pas par un regroupement.

**Décision : le seul ajout est un décideur.** Aucun orchestrateur, aucun générateur de lots,
aucun second chemin d'écriture d'archive.

---

## 3. Le décideur

### 3.1 [NEW] `llm-agents/experiences/decideur_antigravity.py`

Implémente le contrat `Decideur` — rien de plus :

```python
class DecideurAntigravity:
    sans_quota = True                      # runner.py:218 et 973 neutralisent le bloc quota
    modele_verifie = False                 # P1
    def __init__(self, modele: str, echanges: Path, attente_max_s: int, parametres: dict): ...
    async def choisir(self, person, ctx, presentees) -> ReponseDecideur: ...
```

`nom = f"antigravity:{modele}"`. Corps de `choisir`, dans cet ordre :

1. **Payload** — `await agent.build_travel_plan_payload(context, presentees_plans, ctx.purpose,
   ctx.departure_time, ctx.anticipation)`. Constructeur pur, aucun réseau.
2. **Rendu, en processus et sans service** — aucun appel réseau, aucune clé, aucun quota :

   ```python
   from mobility_llm import CATEGORIES, prompt_manager
   modele_item = CATEGORIES["itinary_multi_agent"].item_model          # AgentSpec
   items = [modele_item(**a) for a in payload["agents"]]
   messages = prompt_manager().render("itinary_multi_agent", items, payload["parameters"])
   ```

   `PromptEngine` est une **bibliothèque** sans contenu (Jinja2 + lecture de fichiers ; son
   `__init__` ne prend que des chemins). Le **service** — API HTTP, worker Celery, providers,
   quotas — n'est sollicité que par `llm_client.execute(payload)`, seul appel que ce canal
   supprime. Ne pas passer par `registry.get(...)` : c'est l'objet d'application du gateway
   (`deps.registry` dans `routes.py`), indisponible hors service.

   `mobility_llm.prompt_manager()` est le chemin prévu pour les consommateurs hors gateway
   (contrôleur, expériences, notebooks) et charge le **même bundle** que le gateway découvre par
   entry point (`mobility_llm:bundle`) : mêmes `CATEGORIES_DIR`, `PROMPTS_FILE`, `template_names`,
   `schema_paths`. Surtout, c'est déjà l'objet dont se sert `empreinte_gabarit()`
   (`experience.py:325`) : l'empreinte scellée et le texte transmis au sous-agent sortent du même
   rendu, ce qui est ce qui donne son sens à l'égalité de §8.1.

   C'est donc **le texte exact** que la passerelle aurait fait voir au modèle, schéma de sortie
   inclus. Vérifié le 2026-09-09 hors de tout service : rendu obtenu pour un persona à deux
   options (système 2 316 car., utilisateur 1 036 car.), aucune passerelle démarrée.

   Ce dont ce texte dépend, et comment chaque terme est fixé — c'est ce qui rend l'égalité à
   l'octet (§8.1) atteignable et non seulement souhaitable :

   | Terme | Comment il est fixé |
   |---|---|
   | Ordre des options | `[p.plan for p in presentees]` dans l'ordre reçu : `decision.decider` l'a déjà graîné (D7). C'est la sémantique de `presentation_figee=True` (`llm_agent.py:607`) — le décideur ne remélange jamais |
   | `purpose` de chaque option | posé sur chaque plan avant l'appel, comme `DecideurPasserelle.choisir` |
   | Météo, jour de semaine, graines d'ordre et de tirage | déjà posés **sans condition** par le CLI, hors branche passerelle |
   | `prompt_variant` | seul terme à corriger : `settings.agent.llm_params` n'est peuplé que pour `passerelle` (`cli.py:483`) — cf. §3.4 |
   | Prompt système, template, gabarit d'option | lus par `PromptEngine` dans les fichiers mêmes que hache `empreinte_gabarit` |
3. **Dépôt** — écrit la demande (§4) et attend le verdict, avec `await asyncio.sleep` (jamais
   d'attente bloquante : une seule boucle asyncio sert les 8 personnes).
4. **Lecture** — `normalize_option_probabilities(entries, len(presentees), modes=sent_modes,
   context=…)` puis `draw_index(poids, *graines)`. Même tolérance, même `UniformFallback`,
   même repli D10 que la passerelle.
5. **Trace** — `ReponseDecideur(index=…, fournisseur=self.nom, poids=…, distribution=…,
   reponse_brute=…, presente={"payload": payload, "messages": [m.model_dump() for m in messages]},
   repli_uniforme=…)`. `presente` non vide : exigé par `archive.py:406` (E11).

Ce que le module **ne contient pas** : validateur JSON maison, renormalisation 98–102 %,
réessai avec invite corrective. Les trois faisaient doublon ou changeaient le texte présenté.

### 3.2 [MODIFY] `llm-agents/experiences/experience.py`

- `TYPES_DECIDEUR` (l. 27) : ajouter `"antigravity"` — et au passage `"modele"`, absent alors
  qu'il est dans le `Literal` (désynchronisation existante).
- `DecideurSpec.type` `Literal` (l. 82) : ajouter `"antigravity"`.
- `DecideurSpec.valider()` : `modele` **obligatoire** pour `antigravity`. Sans cette règle, un
  modèle par défaut codé en dur entrerait dans les empreintes sans que personne l'ait choisi.
- `refuser_si_impossible` : la validation de `gabarit.variante` (l. 537) est aujourd'hui réservée
  à `passerelle` ; l'étendre à `antigravity`, qui lit un gabarit lui aussi. Même chose pour
  l'estimation (l. 706) : quota et jetons restent `None` (décideur sans quota), c'est correct.

### 3.3 [MODIFY] `llm-agents/experiences/decideurs.py`

Enregistrement dans `construire_decideur()`, avec import tardif (le décideur importe
`llm_gateway.prompts`) :

```python
if spec.type == "antigravity":
    from experiences.decideur_antigravity import DecideurAntigravity
    if agent is None:
        raise ValueError("un décideur antigravity exige un LlmAgent (construction du payload)")
    return DecideurAntigravity(agent=agent, modele=spec.modele, ...)
```

### 3.4 [MODIFY] `llm-agents/experiences/cli.py`

Six branchements `== "passerelle"` doivent trancher pour `antigravity` :

| Ligne | Décision |
|---|---|
| 292 `_jeu_de_cles_experience` | reste vide : aucune clé API sollicitée |
| 332 moniteur / instances | pas de `MoniteurRessources` : aucun quota à suivre |
| 382 `LlmAgent` | **construit quand même** : il fabrique le payload (aucun envoi) |
| 425 `echantillonnage_decideur` | `True` : c'est un modèle qui répond, la distribution est un tirage |
| 454 refus si aucune instance | ne s'applique pas |
| 483 `llm_params` / `prompt_variant` | **s'applique** : le gabarit de l'expérience doit atteindre `PromptEngine.render` |

---

## 4. Le contrat IPC

### 4.1 Emplacement

`data/experiences/<exp>/executions/<horodatage>/echanges/{demandes,reponses}/`

- Sous le dossier d'exécution : tout ce qui concerne un run vit au même endroit, la reprise (S9)
  retrouve l'état, et l'audit lit les demandes à côté des traces.
- `data/experiences/*/executions/` est déjà dans `.gitignore` (l. 159). `scratch/`, lui, **est
  suivi par git** : y déposer 2 700 prompts les committerait.
- Ce dossier est **exclu du scellement de clôture** (`cloture.sha256`) : ce n'est pas un artefact
  de résultat, et son contenu fait doublon avec `presente` dans `decisions.jsonl`.

### 4.2 Nommage et atomicité

Un fichier par déplacement, jamais un lot :

```
demandes/<person_id>__<activity_id>.json
reponses/<person_id>__<activity_id>.json
```

- **Écriture atomique obligatoire des deux côtés** : écrire `<nom>.json.tmp` puis `os.replace()`.
  Un lecteur ne doit jamais tomber sur un JSON tronqué.
- Le décideur écrit la demande, **puis** sonde `reponses/` toutes les `PAS_SONDAGE_S = 0.5 s`
  (`await asyncio.sleep`).
- Après lecture d'une réponse, le décideur déplace la demande dans `demandes/traitees/` :
  ce qui reste dans `demandes/` est exactement ce qui attend l'agent.

### 4.3 Forme d'une demande

```json
{
  "version": 1,
  "person_id": "1234", "activity_id": "a7",
  "modele_attendu": "gemini-3.8-flash",
  "n_options": 4,
  "messages": [{"role": "system", "content": "…"}, {"role": "user", "content": "…"}],
  "schema_sortie": { "…": "output_schema.json de la catégorie" }
}
```

`messages` est le rendu de `PromptEngine.render`, **verbatim**. Règle d'usage, aussi
contraignante que le code : l'agent Antigravity transmet ces messages au sous-agent sans
préambule, sans reformulation, sans consigne ajoutée. Toute addition rend fausse l'empreinte
de gabarit scellée dans `execution.yaml` (§b du rapport de relecture).

### 4.4 Forme d'une réponse

```json
{
  "version": 1,
  "person_id": "1234", "activity_id": "a7",
  "modele_declare": "gemini-3.8-flash",
  "sortie_litterale": "…la sortie du sous-agent TELLE QU'ÉMISE, verbatim…",
  "reponse_brute": "…texte intégral rendu par le sous-agent…",
  "agents": [{"agent_id": "1234", "probabilities": [{"index": 0, "mode": "car", "probability": 60, "reason": "…"}]}]
}
```

- `person_id` / `activity_id` **doivent** correspondre au fichier lu ; sinon la réponse est
  rejetée (`erreur = "antigravity: réponse hors sujet"`) et l'attente continue.
- `modele_declare` différent de `modele_attendu` → compté dans `erreurs_par_type`, la décision
  est refusée. C'est le seul contrôle possible : une déclaration comparée à une déclaration.
- `reponse_brute` est conservée intégralement dans la trace, comme pour la passerelle.
- **`sortie_litterale` (P8, ajouté le 2026-09-10) — la sortie du sous-agent telle qu'émise,
  verbatim.** Constat de l'audit du 2026-09-10 sur `exp_agy-gemini-38-f` : les 2 287
  `reponse_brute` du run étaient du JSON nu, sans une balise markdown ni une ligne de prose, et
  sous **deux formes structurelles différentes** selon le segment (232 à plat, 2 055 enveloppées
  dans `agents`). C'était donc une re-sérialisation par l'agent intermédiaire, et aucune pièce
  de l'archive ne montrait ce que le modèle avait réellement écrit — la seule chose qui aurait
  pu étayer P3. Le champ est **transmis tel quel** dans la trace, jamais normalisé, jamais
  replié sur `reponse_brute` : `null` quand l'agent ne le fournit pas. Un trou déclaré vaut
  mieux qu'une copie qu'on prendrait pour la sortie du modèle. Les réponses sans ce champ sont
  comptées (`sans_sortie_litterale`) et signalées une fois, sur front montant.

### 4.5 Attente, délai, fin de run

- Délai maximal par déplacement : `exp.attente_max_s` (120 s par défaut,
  `DEFAUTS_NOMMAGE`), et non une constante nouvelle.
- **Nouvel état typé** `ETAT_EN_ATTENTE_AGENT`, sur le modèle de `ETAT_EN_ATTENTE_QUOTA` :
  sans lui, un run où l'agent s'est arrêté s'affiche `en_cours` indéfiniment au tableau de bord.
  L'état est posé quand une demande dépasse `attente_max_s / 4` et levé à la première réponse.
- Dépassement de `attente_max_s` → `ReponseDecideur(index=None, erreur="antigravity: pas de
  réponse en <n> s")`. Le runner traite déjà cette non-réponse comme une erreur réessayable :
  aucun repli fabriqué, aucune décision inventée (RG-2).
- Interruption (`PAUSE` / `STOP` / SIGINT) : l'attente est interruptible à chaque pas de
  sondage, comme `_attendre_fenetre_quota`.

### 4.6 Qui pilote

Fait technique : **un script Python ne peut pas appeler `invoke_subagent`**. Le partage est donc
asymétrique et sans ambiguïté :

- Le **processus Python** (`make experience-lancer`) est le moteur métier : il ordonne, dépose,
  attend, valide, archive. Il ne sait rien d'Antigravity.
- L'**agent Antigravity** est un service : il boucle sur `demandes/`, appelle un sous-agent par
  fichier, écrit `reponses/`. Il ne décide de rien.

L'ordre de démarrage est libre : une demande déposée avant que l'agent ne boucle sera servie au
premier passage, et l'agent qui démarre à vide sonde jusqu'à la première demande.

### 4.7 Journalisation

- Début : nombre de déplacements attendus, dossier d'échanges, modèle déclaré.
- Toutes les 30 s : demandes en attente, âge de la plus ancienne, réponses servies.
- `[ALARME]` sur front montant quand aucune réponse n'arrive depuis `attente_max_s`, ou quand
  les rejets (`hors sujet`, `modele_declare` inattendu) dépassent 1 % — deux symptômes d'un
  agent mal câblé, à voir tout de suite et pas après trois heures.
- Fin : succès explicite avec durée, décidés, replis, rejets, délais dépassés.

---

## 5. Nommage canonique

La v1 annonçait `exp_agy-38-fl_minper_jtir_t0_nosim`. Ce nom **ne peut pas être produit** :
`segment_decideur` ne renvoie un slug de modèle que pour `passerelle` (`nommage.py:179`), et
`segments()` n'ajoute la variante et la température que sous la même condition (l. 211 et 259).
Le nom obtenu serait `exp_agy_jtir_nosim` — comme `exp_alea_nosim` ou `exp_majvoiture_nosim`.
Et deux runs `antigravity` sur deux modèles porteraient le même nom de base, distingués par un
simple `_2` : le modèle disparaîtrait de l'identité de l'expérience (contraire à N3/N4).

**Correction** — `antigravity` rejoint la famille « nommée par son modèle », en gardant son type
visible puisque le modèle n'est pas vérifié :

- `ABREV_DECIDEUR["antigravity"] = "agy"`.
- `segment_decideur` : pour `antigravity`, renvoyer `f"agy-{abreger_modele(dec['modele'])}"`, et
  lever `NommageImpossible` si `modele` est vide (même message que pour la passerelle).
- `segments()` : traiter `antigravity` comme `passerelle` aux trois endroits — variante de
  gabarit (l. 211), température (l. 259), et validation de variante côté `experience.py`.

Nom obtenu, vérifié contre le code : **`exp_agy-gemini-38-f_minper_jtir_t0_nosim`** (40 car.,
conforme à `MOTIF_NOM`). Aucun renommage rétroactif : le `nom` écrit dans un `experience.yaml`
existant reste autoritaire (N12).

---

## 6. Emplacement des résultats

La v1 écrivait les exécutions dans `data/experiences/exp_gemini-31-fl_minper_jtir_t0_nosim/`,
ce qui contredisait son propre §2 et la spec de nommage : le nom **est** l'identité (N2/N10), et
une exécution dont le décideur n'est pas celui de la définition n'est pas une exécution de cette
expérience.

**Correction** — le canal `antigravity` passe par le chemin normal : `make experience-definir`
crée `data/experiences/exp_agy-gemini-38-f_minper_jtir_t0_nosim/`, `make experience-lancer` y
écrit `executions/<horodatage>/`. La comparaison avec l'expérience passerelle se fait ensuite
entre deux dossiers distincts — c'est exactement ce que `registre.comparer` sait faire, par
empreintes et jamais sur la foi des noms (RG-4).

---

## 7. Anomalies et repli

Alignement strict sur D10, sans niveau supplémentaire :

| Situation | Traitement | Compteur |
|---|---|---|
| Probabilités en % ou en fractions, index dupliqués, négatifs, option non notée | `normalize_option_probabilities` (déjà) | — |
| Index hors bornes | réalignement par mode envoyé (déjà) | — |
| Vecteur absent ou masse nulle | `UniformFallback` → `METHODE_REPLI_UNIFORME` | `replis_uniformes` |
| JSON illisible, `person_id` faux, `modele_declare` inattendu | réponse refusée, attente poursuivie | `erreurs_par_type` |
| Aucune réponse en `attente_max_s` | non-réponse réessayable, rien n'est fabriqué | `erreurs_par_type` |

Supprimé de la v1 : les « 2 retries avec invite de correction de syntaxe ». Réécrire l'invite
change le texte présenté, donc la trace ne dit plus ce que le modèle a vu et la décision n'est
plus comparable. Supprimé aussi : `rapport_anomalies_antigravity.md`. Les compteurs existants
(`erreurs_par_type`, `replis_uniformes`, `couverture`) portent déjà l'information, `make error`
la sort, et un second fichier de vérité se désynchronise du premier.

### 7.1 Gabarit non figé : avertissement, pas refus (décision du 2026-09-09)

Sans `gabarit.variante`, `prompt_manager()` prend le **prompt actif du jour**
(`abreger_variante(None)` → `actif` : « celui du jour, pas un réglage »). Les 23 expériences
définies qui lisent un prompt nomment toutes une variante figée ; `null` n'apparaît que sur les
trois décideurs locaux, pour qui le gabarit ne veut rien dire.

Ce canal **n'interdit pas** la variante absente : l'essai rapide avec le prompt du jour est
précisément l'usage banc d'essai que P2 lui reconnaît. Il l'**annonce** :

- WARNING au lancement quand `gabarit.variante` est absente, **nommant le sha256 du prompt
  actif** retenu — l'archive scelle déjà ce hash (`experience.py:406`), le journal le rend
  visible avant trois heures de run plutôt qu'après.

Le danger réel est ailleurs, et **hors périmètre de ce plan** : rien n'empêche aujourd'hui
d'ajouter une exécution à une expérience dont les exécutions précédentes portent un **autre**
sha256 de gabarit. `signature()` hache la définition, qui contient `variante: null` dans les deux
cas → même signature, même nom, et `attribuer_nom` renvoie `reutilise` : deux prompts différents
se rangent silencieusement sous une seule identité d'expérience (N10 en défaut). Aucun contrôle
dans `runner.py` ni `archive.py` ; le seul endroit qui compare ce hash est `jetons_mesures`.
Cela concerne **la passerelle autant qu'Antigravity** → ticket séparé, pas de correction
introduite ici par la petite porte.

---

## 8. Plan de validation

### 8.1 Tests unitaires et de contrat

- `DecideurSpec` : `type: antigravity` accepté ; `modele` absent → refus nommant le champ.
- Nommage : `segment_decideur({"type": "antigravity", "modele": "gemini-3.8-flash"})` →
  `agy-gemini-38-f` ; nom complet → `exp_agy-gemini-38-f_minper_jtir_t0_nosim` ; `modele` vide →
  `NommageImpossible`.
- **Identité du texte présenté** (le test qui compte) : pour un même déplacement et un même
  gabarit, les `messages` écrits dans la demande sont **octet pour octet** ceux que
  `PromptEngine.render` produit pour le payload de la passerelle.
- IPC : réponse au mauvais `person_id` → refusée, attente poursuivie ; JSON tronqué → refusée ;
  `modele_declare` inattendu → refusée et comptée ; timeout → non-réponse, aucune décision
  fabriquée ; interruption pendant l'attente → sortie propre.
- Trace : `presente` non vide et `modele_verifie: false` sur chaque décision ;
  `valider_archive()` sans problème.

### 8.2 Intégration sur mini-cohorte

10 personnes, environ 27 déplacements, avec un faux agent (script de test qui remplit
`reponses/` depuis un fichier de verdicts figés) : dossier d'exécution créé, `decisions.jsonl`
et `moves.csv` complets, `valider_archive()` vert, `registre.lister()` et le tableau de bord
affichant `antigravity:<modele>` et le drapeau non vérifié.

### 8.3 Comparaison avec l'exécution passerelle — reformulée

La v1 demandait de retrouver voiture ≈ 46 %, TC ≈ 31 %, marche ≈ 14 %, vélo ≈ 8 %. Ce sont
**exactement** les parts de `exp_gemini-31-fl_minper_jtir_t0_nosim/executions/2026-09-07_21_29_24`
(46,45 / 30,79 / 14,33 / 8,27). Exiger d'un autre décideur qu'il les retrouve, c'est valider en
ajustant sur le résultat connu : le critère ne peut alors ni échouer utilement, ni rien apprendre.

Ce qui est vérifié à la place :

```bash
make comparer \
  A=data/experiences/exp_gemini-31-fl_minper_jtir_t0_nosim/executions/2026-09-07_21_29_24 \
  B=data/experiences/exp_agy-gemini-38-f_minper_jtir_t0_nosim/executions/<horodatage>
```

1. **Comparabilité déclarée** : `comparer` annonce « comparables » — les empreintes partagées
   (population, jeu, calendrier, `graine_ordre`, `graine_tirage`, tolérances, `max_candidats`)
   sont identiques, et le gabarit de même catégorie a le même sha256. Le décideur n'entre pas
   dans les champs partagés, par construction.
2. **Complétude** : couverture de B ≥ celle de A à décideur non sollicité près ; aucun
   déplacement attendu sans trace ; `sans_solution` et `choix_unique` **identiques** à A
   (8 et 331) — ils ne dépendent pas du décideur, un écart signalerait un jeu ou un filtre
   différent, pas un modèle différent.
3. **Honnêteté de l'archive** : `modele_verifie: false` présent, `replis_uniformes` et
   `erreurs_par_type` publiés, aucun `[ALARME]` non expliqué dans `make error`.
4. **Coût** : bloc quota vide, `sollicitations` cohérent avec les décisions non resservies.

Les parts modales de B sont **rapportées, pas contraintes**. Un écart avec A se lit comme ce
qu'il est : deux modèles différents (`gemini-3.1-flash-lite-preview` contre un modèle déclaré et
non vérifié), donc une différence sans interprétation possible tant que P1 tient.

Note sur la référence : `2026-09-07_21_29_24` est une exécution **reprise**
(`resservies: 1548` pour `sollicitations: 1034`), et ses compteurs disent `decides: 2637` sur
`attendus_exploitables: 2645` — 2 693 est le nombre de lignes de trace, dont 331 choix uniques,
8 sans solution et 48 inexploitables exclus des attendus. Reprendre ce vocabulaire, pas « 2 693
décisions ».

---

## 9. Documentation et changelog

À faire dans la même livraison, pas après :

- `docs/arch/plateforme-experiences.md` — ajouter `DecideurAntigravity` à la liste des décideurs
  (l. 242), avec P1/P2 énoncés noir sur blanc.
- `docs/changelog.md` — entrée en tête, format `## [AAAA-MM-JJ] Titre fonctionnel`, avec un bloc
  Avant / Après sur ce que le canal permet et ce qu'il interdit.
- `specs/nommage-canonique-experiences.md` — la table des abréviations gagne `agy`, et la règle
  « nommé par son modèle » s'énonce pour deux types au lieu d'un.
- `scripts/dashboard/experiences.py:108` `TYPES_DECIDEUR` — ajouter `antigravity` (et
  `majoritaire_voiture`, absent) : sans quoi la promesse de visibilité au tableau de bord est vide.
- `scripts/analysis/plot_experiences.py:74` — libellé et marqueur.

---

## 10. Questions ouvertes

Consignées ici plutôt que tranchées à la place de l'auteur :

1. **Q1** — Un run `antigravity` doit-il apparaître dans `make registre` au même rang que les
   autres, ou dans une section « non vérifiés » ? P2 plaide pour la seconde, l'ergonomie pour la
   première.
2. **Q2** — `echanges/` doit-il être purgé à la clôture ? Argument pour : 2 700 × 2 fichiers de
   prompt font doublon avec `presente`. Contre : c'est la seule preuve de ce qui a circulé si un
   doute surgit sur le câblage de l'agent.
3. ~~**Q3** — Refuser une expérience `antigravity` sans `gabarit.variante` figée ?~~
   **Tranchée le 2026-09-09 : avertir, ne pas refuser.** Voir §7.1.

---

## Annexe A — écarts de la v1

| # | Écart v1 | Traitement v2 |
|---|---|---|
| 1 | Modèle annoncé comme épinglé, en réalité invérifiable | §1 : `modele_verifie: false`, P1/P2/P3 |
| 2 | Prompt écrit par l'agent principal, empreinte de gabarit fausse | §3.1 étape 2, §4.3 verbatim, test §8.1 |
| 3 | `exp_agy-38-fl_minper_jtir_t0_nosim` impossible à produire | §5, nom corrigé et vérifié |
| 4 | Résultats rangés sous l'expérience passerelle | §6, définition et dossier propres |
| 5 | Lots de 8, ordonnanceur et orchestrateur réécrits | §2 : le runner tient déjà S4/D4 |
| 6 | Contrat IPC absent, deux jeux de chemins contradictoires | §4 en entier |
| 7 | Validateur JSON et renormalisation 98–102 % en doublon | §3.1 étape 5, §7 |
| 8 | Retries avec invite corrective | supprimés (§7) |
| 9 | Parts modales de référence érigées en critère | §8.3 reformulé |
| 10 | Chiffres (« 2 693 décisions ») | §8.3, note finale |
| 11 | Points de branchement manqués (4 registres de types, CLI, doc) | §3.2, §3.4, §9 |
| 12 | `scratch/` comme dossier d'échanges (suivi par git) | §4.1 |
