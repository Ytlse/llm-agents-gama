# Ticket 100 — plan d'architecture des sept lots

Écrit le 2026-09-21. **Aucune ligne de code n'est écrite avant validation de ce plan** (règle
plan-first). Contrat de tests : [`tests.md`](tests.md). Questions vivantes :
[`questions.md`](questions.md).

Ticket : [`docs/tickets/ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md`](../../docs/tickets/ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md).

---

## 1. Ce qui a été vérifié dans le code avant d'écrire ce plan

Le ticket décrit l'aval comme « commun » et l'amont comme « une copie ». C'est exact, mais cinq
points de détail décident de la forme du paquet, et trois d'entre eux n'étaient pas prévus au
ticket. Tout ce qui suit a été lu, pas supposé.

| # | Constat | Où | Ce qu'il change au plan |
|---|---|---|---|
| V1 | **`Person` ne porte pas `household.id`.** Le JSON de population le porte à la racine (`household: {id, iris_id, commune_id}`) ; `Person.model_validate` ignore les clés inconnues (`world/population.py:219`) et le seul lecteur du dépôt est `inputs/population/perimeter.py`, qui travaille sur le dict **brut** | `models.py:285`, `world/population.py:219` | **Bloquant.** La règle `foyers` (lot 2) et tout le lot 4 lisent un identifiant que le runtime n'a pas. Remonté au **lot 1**, pas au lot 4 |
| V2 | **La prise `arrivee` n'écrit pas d'entrée : elle en ANNEXE une.** Le vécu est joint au texte d'observation (`ob_text = f"{ob_text}\n[ INCIDENT ] {vecu}"`) et la gravité porte la **somme** des deux retards — mesuré et injecté | `simulation_controller.py:2102`, `:2168` | « Une seule fonction dépose l'entrée » ne peut pas être littéral. `deposer()` a deux gestes, `joindre` et `poser` (§ 4) — sans quoi le test en or échoue par construction |
| V3 | `gravite_jugee()` retombe **silencieusement** sur `None` + WARNING quand le modèle rend un échelon hors grille | `llm/gravite.py:268-292` | Le refus franc du lot 3 (059 Q17) ne peut pas s'y mettre : la fonction est partagée avec la réflexion nocturne, où le repli est voulu. Le refus vit dans `evenements/jugement.py` |
| V4 | `MemoryEntry.from_dict` **ignore** les clés inconnues, par garantie de réversibilité | `llm/memory.py:from_dict` | Ajouter `origine` est réversible sans migration. Un run repris sous l'ancien code perd le champ, il ne casse pas |
| V5 | La version du schéma de réflexion entre dans la clé de mémoïsation (`SCHEMA_REFLEXION_VERSION = 3`) | `agents/llm_agent.py:533`, `llm/reflection_store.py:81` | Le lot 4 l'incrémente à **4**. Sans cela, une réponse mémoïsée sans champ de provenance serait servie et toutes les croyances passeraient pour vécues |
| V6 | `add_short_term_memory` ne transporte **ni la valence ni l'origine** : `add_message` construit la `MemoryEntry` avec les seuls axes et l'importance | `agents/llm_agent.py:647`, `llm/shortterm.py:20-55` | Deux paramètres à ajouter le long du même chemin, `valence` et `origine`. Aucune autre couche à traverser |
| V7 | `gel_actif()` coupe **toute** écriture de mémoire courte pendant le rejeu d'une reprise à chaud | `agents/llm_agent.py:660` | Un événement dont le jour tombe dans la fenêtre de rejeu serait perdu **en silence**. Refus au chargement + `[ALARME]` (§ 5, R32) |
| V8 | `test_079_chocs.py` : **36 tests collectés** (le ticket en annonce 34 — 28 fonctions, dont plusieurs paramétrées) | `pytest --collect-only` | Le contrat dit 36, et aucun attendu ne bouge |
| V9 | Le corpus du 059 lot 1 **est au dépôt** — `articles_txt/{a07,a09,a13,a18,a25}/brut.txt` + `MANIFEST.yaml` avec les empreintes `fr` et `en` — mais non commité | `docs/paper/sources/actualites/` | Le lot 2 n'attend rien. Sa garde de citation compare à `MANIFEST.yaml`, pas à une constante |
| V10 | Le conteneur `controller` ne monte **pas** `docs/paper/sources/` | `infra/docker-compose.yml:496-509` | Le lot 2 ajoute un montage étroit en lecture seule, sur le modèle exact de `experience_plan` déjà présent |
| V11 | `moves.csv` porte déjà `Contrainte de chaîne`, `Choc`, `Jour relatif au choc` | `utils/move_logger.py:111,154` | Le lot 5 **renomme** deux colonnes. Quatre lecteurs à suivre (§ 8) |
| V12 | `experiences/experience.py` refuse l'exécution des deux types d'événement (`incident`, `information`) au titre de E6 | `experiences/experience.py:677-680` | Le lot 6 lève le refus pour les deux, pas pour un seul : après ce ticket, les deux passent par le même canal |

---

## 2. Ordre d'exécution

```
  L0 plan + contrat + questions ──► VALIDATION HUMAINE
        │
        ▼
  L1 paquet evenements/ · prise arrivee · household_id sur Person · origine
     · migration des six cas · TEST EN OR
        │
        ├──────────────► L3 jugement à l'injection (les deux canaux)
        │                     │
        ├──► L2 prise reveil · canal lu · citation · foyers · fenêtre tirée
        │          │          │
        │          └──────────┴──► L4 foyer : récit du soir · croyances · provenance
        │                                │
        └────────────────────────────────┴──► L5 sorties · mesure · figure
                                                        │
                                                        ▼
                                              L6 leviers · doc · changelog
```

**L1 avant tout, et il ne doit rien casser.** Il ne livre aucune fonction nouvelle : il déplace
`chocs.py` dans un paquet, lui ajoute deux champs, et prouve par le test en or que le run du
§ 7.2 rendrait le même fichier. Un lot qui n'ajoute rien est le seul endroit où une migration se
vérifie.

**L2 et L3 sont indépendants** et peuvent se mener dans n'importe quel ordre. L3 ne dépend du
canal `lu` que pour sa deuxième moitié ; sa première moitié (jugement d'un choc, ablation
déclarée) tient sur L1 seul.

**L4 est le seul lot lourd**, le seul qui touche un prompt, et le seul derrière un drapeau
éteint par défaut.

---

## 3. Lot 1 — le paquet, la prise `arrivee`, la migration

### Fichiers

| Fichier | Nature |
|---|---|
| `services/llm-agents/llm/evenements/__init__.py` | **neuf** — façade : `initialiser`, `registre`, `reinitialiser`, `incident_reseau_a_une_source` |
| `services/llm-agents/llm/evenements/declaration.py` | **neuf** — dataclasses gelées + `charger()` + `RefusDEvenement` |
| `services/llm-agents/llm/evenements/gardes.py` | **neuf** — marqueurs de consigne, verdict, intention, deuxième personne |
| `services/llm-agents/llm/evenements/exposition.py` | **neuf** — `mode`, `agents`, `tirage` (la règle `foyers` arrive au lot 2) |
| `services/llm-agents/llm/evenements/calendrier.py` | **neuf** — `jour_du_run`, `jour_relatif`, `jours_dus` |
| `services/llm-agents/llm/evenements/registre.py` | **neuf** — `RegistreEvenements` |
| `services/llm-agents/llm/evenements/injection.py` | **neuf** — `a_l_arrivee()` ; `au_reveil()` au lot 2 |
| `services/llm-agents/llm/chocs.py` | **adaptateur** : réexporte les noms du 079 en journalisant une dépréciation. Supprimé au lot 6 |
| `services/llm-agents/llm/memory.py` | `MemoryEntry.origine` |
| `services/llm-agents/llm/shortterm.py`, `agents/llm_agent.py` | `valence` et `origine` le long de `add_short_term_memory` |
| `services/llm-agents/models.py`, `world/population.py`, `inputs/population/eqasim_loader.py` | `Person.household_id` |
| `services/llm-agents/settings.py` | `EvenementsConfig{enabled, fichier}` ; `chocs:` conservé comme alias déprécié |
| `services/llm-agents/config/evenements/*.yaml` + `README.md` | **neufs** — les six cas migrés |
| `services/llm-agents/tests/test_100_lot1_migration.py` | **neuf** — dont le test en or |

### Les dataclasses

Reprises telles quelles de `chocs.py`, renommées et élargies. Gelées (`frozen=True`), comme au 079.

| Classe | Champs | Note |
|---|---|---|
| `Evenement` | `evenement_id, libelle, source, canal, moment, texte, effet_physique, jugement, calendrier, exposition, cadence, empreinte` | `canal ∈ {vecu, lu}`, `moment ∈ {arrivee, reveil}` |
| `Texte` | `jours: dict[int, str]` **ou** `fichier: Path, sha256: str, contenu: str` | Les deux formes s'excluent ; un texte cité est lu **une fois** au chargement et gardé en mémoire |
| `EffetPhysique` | `retard_min, incident_reseau, correspondance_ratee` — par jour | `None` = le monde ne bouge pas. Distinct d'un effet **à zéro**, qui est un fait mesuré nul |
| `Calendrier` | `jours: tuple[int, ...]` **ou** `fenetre_jours: (a, b), graine: int` | La fenêtre est tirée par **cible** au lot 2 |
| `Exposition` | `regle, modes, part, graine, agents, foyers, lecteurs_par_foyer` | `foyers` et `lecteurs_par_foyer` déclarés dès L1, **refusés** tant que la règle `foyers` n'existe pas |
| `EvenementApplique` | `evenement_id, canal, moment, jour_run, jour_relatif, texte, effet_physique, raison` | Ce que la prise rend au contrôleur |

### Le chargeur accepte les deux formats

`charger()` détecte la clé de tête : `evenement:` → format 100 ; `choc:` → format 079, converti
à la volée vers `canal: vecu`, `moment: arrivee`, `texte.jours`, `effet_physique` par jour, avec
une ligne `logger.warning` nommant le fichier. Les huit déclarations de `config/chocs/` continuent
donc de se charger sans être touchées — c'est la condition du test en or, qui doit pouvoir rejouer
**le fichier d'origine**, pas sa traduction.

### La prise `arrivee` : ce qui change, et ce qui ne change pas

Rien ne change. L'appel du contrôleur passe de `chocs_module.registre()` à
`evenements.registre()`, `applique()` rend un `EvenementApplique` au lieu d'un `ChocApplique`, et
le texte reste **joint** à l'observation sous le même préfixe `[ INCIDENT ]` (V2). La gravité
continue de porter la somme des deux retards, `tracer()` écrit les mêmes champs.

⚠ **`deposer()` a donc deux gestes, et le ticket ne le disait pas.**

| Geste | Qui l'appelle | Ce qu'il fait |
|---|---|---|
| `joindre(ob_text, applique)` | prise `arrivee` | annexe le texte à l'observation en cours ; la `MemoryEntry` reste **celle de l'arrivée**, qualifiée par la gravité fusionnée |
| `poser(person_id, texte, importance, valence, axes, origine)` | prise `reveil` (lot 2) | écrit une entrée **autonome** en mémoire courte, sans observation associée |

Ce qui est commun, et c'est le vrai gain du ticket, ce n'est pas l'écriture : c'est la
**qualification** — `gravite_concept(estimée, déterministe)`, la valence, l'origine, les axes, la
force, la durée de service. Une seule fonction `qualifier()`, appelée par les deux gestes.

### `origine` sur `MemoryEntry`

```python
# Provenance de l'entrée (ticket 100, D2). `None` = entrée écrite avant ce ticket : elle se LIT
# comme « vécue », faute de mieux, mais elle ne le DÉCLARE pas — la distinction compte le jour
# où l'on voudra savoir combien d'entrées sont antérieures au champ.
origine: Optional[str] = None   # "vecu" | "lu" | "entendu"
```

`origine_effective` rend `self.origine or "vecu"`. Le champ ne filtre rien au lot 1 : il est
écrit, journalisé, et c'est tout. Il ne devient une règle qu'au lot 4.

### `household_id` sur `Person` (V1)

`Person.household_id: Optional[str] = None`, renseigné aux **deux** chemins de chargement :
`world/population.py` (format pydantic) et `inputs/population/eqasim_loader.py`. Recopié depuis
`household.id` du dict brut avant validation.

Une `[ALARME]` au démarrage si **aucun** agent ne le porte alors qu'une règle `foyers` ou le
partage au foyer est actif : vingt foyers déclarés sur une population sans identifiant produiraient
un run entier sans un seul lecteur et sans le moindre symptôme.

### Le test en or

Rejouer `config/chocs/c6_voiture_suspecte.yaml` sur le nouveau paquet, jugement éteint, et exiger
un `evenements.jsonl` **égal champ à champ** à `chocs.jsonl` — aux deux seuls champs nouveaux près
(`canal: vecu`, `moment: arrivee`), qui sont ajoutés et non substitués. Les 36 tests du 079
tournent sans modification de leur attendu, par import de l'adaptateur.

**Ce que le test en or ne prouve pas** : il rejoue une trace, pas un run. Il ne dit rien du
chemin GAMA. C'est pour cela que le lot 6 demande un run court de non-régression sur c6 avant de
supprimer `chocs.py`.

---

## 4. Lot 2 — la prise `reveil`, le canal `lu`, la citation, les foyers

### Fichiers

| Fichier | Nature |
|---|---|
| `llm/evenements/injection.py` | `au_reveil()` |
| `llm/evenements/gardes.py` | `verifier_empreinte()` — la garde propre au canal `lu` |
| `llm/evenements/exposition.py` | règle `foyers` + `lecteurs_par_foyer` |
| `llm/evenements/calendrier.py` | fenêtre tirée par cible |
| `urban_mobility_agents/simulation_controller.py` | un appel à la bascule de journée |
| `config/evenements/a{07,09,13,18,25}_*.yaml` | **neufs** — les cinq articles du 059 déclarés |
| `infra/docker-compose.yml` | montage `articles_txt` en lecture seule (V10) |
| `tests/test_100_lot2_canal_lu.py` | **neuf** |

### Le point d'injection

À la bascule de journée du contrôleur, dans `_on_sync`, au **même jalon de 3 h simulées** que le
point de reprise (`_next_checkpoint_ts(timestamp, 3)`), donc :

- après le drainage nocturne des réflexions et le plancher de 22 h, sur des tampons vides ;
- **avant** le premier réveil de la journée, donc avant la première décision — c'est la définition
  du régime, et c'est ce qui le sépare du choc ;
- idempotent par journée, sur le modèle exact de `_tirer_accidents_du_jour`.

⚠ **Piège du gel (V7).** Pendant le rejeu d'une reprise à chaud, `gel_actif()` renvoie `poser()`
sans rien écrire. Un article dont le jour tombe dans la fenêtre de rejeu disparaîtrait en silence.
`initialiser()` refuse au chargement si un jour dû est antérieur au point de reprise, et lève une
`[ALARME]` si le gel est actif au moment d'une injection due.

### La garde de citation

`texte.sha256` déclaré ⇒ le fichier est lu, son empreinte calculée, et comparée **à la
déclaration** et **au `MANIFEST.yaml` du corpus** quand le fichier vit sous `articles_txt/`. Trois
valeurs, deux comparaisons : une déclaration juste contre un manifeste faux se voit aussi.

Le texte servi porte la mention `Translated from French` à l'intérieur de l'entrée, décision du
059 lot 1, et la mention entre dans l'empreinte — elle est une information que l'agent a, pas un
commentaire de dépôt.

Préfixe de l'entrée : `[ PRESSE ] This morning I read in the paper: « … »`.

### La règle `foyers`

```
lecteurs(evenement, population) :
    pour chaque household_id déclaré :
        membres = [p pour p dans population si p.household_id == hid et non p.immobile]
        refus si membres est vide                      → [ALARME], le foyer n'existe pas
        tri par person_id (ordre numérique, comme extraire_sous_population)
        tirage de `lecteurs_par_foyer` par hachage f"{graine}:{evenement_id}:{hid}:{rang}"
        journalise : foyer, lecteur retenu, membres écartés
```

Déterministe, stable d'un run à l'autre, indépendant de l'ordre d'arrivée des observations — la
propriété que la règle `tirage` du 079 tenait déjà, et pour la même raison.

### La fenêtre tirée

`jour_tire(cible) = a + H(f"{graine}:{evenement_id}:{cible}") mod (b - a + 1)`, la cible étant le
`household_id` sous la règle `foyers` et le `person_id` ailleurs. Deux foyers ne lisent pas le même
jour : un effet de calendrier ne peut plus se confondre avec celui de l'article.

### Les refus propres au canal

| Refus | Pourquoi |
|---|---|
| empreinte ≠ fichier, ou ≠ manifeste | le texte est cité, jamais réécrit |
| `effet_physique` non nul sur `canal: lu` + `moment: reveil` | le monde ne change pas avant la décision (§ 9 du ticket) |
| `foyers` déclarés et `household_id` absent de toute la population | V1 — sinon, run entier sans lecteur et sans symptôme |
| foyer déclaré absent, ou sans membre mobile | idem |
| fenêtre `[a, b]` avec `b < a`, ou hors run | une fenêtre vide ne tire rien |

---

## 5. Lot 3 — le jugement à l'injection

### Fichiers

| Fichier | Nature |
|---|---|
| `llm/evenements/jugement.py` | **neuf** |
| `packages/mobility_llm/src/mobility_llm/categories/evenement_jugement/{template.md.j2,output_schema.json}` | **neufs** |
| `config/llm_gateway/…` (table de routage) | la catégorie `evenement_jugement` déclarée |
| `tests/test_100_lot3_jugement.py` | **neuf** |

### L'échelle, et rien d'autre (D3)

Le schéma de sortie reprend **exactement** les énumérations de `stm_reflection` :
`severity ∈ {negligible, noticeable, inconvenient, serious, memorable}`,
`valence ∈ {negative, neutral, positive}`, `mode` en **liste** sur la hiérarchie canonique plus
`any`. Les ancres textuelles sont celles de `llm/gravite.py:ANCRES`, recopiées depuis la constante
et non réécrites dans le gabarit — la leçon du lot A du 077 : deux vocabulaires qui divergent sans
que rien ne le dise.

La grille à neuf échelons signés du 059 (troisième tour) est **retirée**. Elle se relit dans les
cinq intensités croisées avec la valence, sans perte : quatre négatifs, un centre, quatre positifs.

### Le refus franc (059 Q17)

`jugement.py` n'appelle **pas** `gravite_jugee()` (V3). Il résout l'échelon sur `NIVEAUX` et
`ALIAS_NIVEAUX` et, hors grille ou absent :

```python
logger.error(
    f"[ALARME] [evenements] « {evenement_id} » : le modèle a rendu l'échelon « {brut} », "
    f"hors des cinq échelons {sorted(NIVEAUX)}. Aucun repli n'est appliqué : l'exposition de "
    f"{person_id} au jour {jour} N'A PAS EU LIEU. Ne pas la compter dans l'analyse."
)
```

Aucune valeur de remplacement, aucun échelon médian, aucune retombée sur la gravité déterministe.
Un repli silencieux fabriquerait une exposition qui n'a pas été jugée et la compterait comme les
autres.

### La règle du maximum est retirée (D7, 2026-09-22) — **appliquée au code le jour même**

`importance_retenue = importance_estimee`, dans les deux canaux. Le terme déterministe n'entre
plus dans le calcul de la gravité.

⚠ **Ce paragraphe disait l'inverse jusqu'au 22 septembre** — « le fait mesuré reste le plancher
[…] elle n'est pas rouverte ». Ce qui change : `evenements/jugement.py` n'appelle plus
`gravite_concept` avec le terme déterministe, il retient `borne_0_1(estimee)`. Ce qui ne change
pas : `gravite_concept` reste en service pour les concepts, où le plancher du groupe consommé
est une règle de la mémoire hors du périmètre de ce ticket, et le bras `jugement: aucun` retombe
toujours sur la gravité déterministe — il en devient **le seul chemin**.

**La garde de remplacement est livrée avec la décision** (§ 5 bis du ticket, Q15). L'écart
`estimée − déterministe` est calculé à chaque jugement, porté par `Jugement.ecart_au_fait`,
écrit dans `evenements.jsonl` sous la colonne du même nom, et une `[ALARME]` se lève quand
l'agent sous-estime de plus de `memoire__ecart_jugement_alarme` (0,30). **Elle ne corrige
jamais la valeur** : corriger en silence rétablirait le plancher sous un autre nom, et la
campagne mesurerait de nouveau la garde au lieu de l'agent. Le seuil vaut plus d'un échelon —
les marches de l'échelle valent 0,20 à 0,25, donc un tel écart ne vient pas d'une hésitation
entre deux niveaux voisins ; « anodin » sur un dépannage de trente minutes vaut −0,60.

**Le terme déterministe ne disparaît pas du dispositif** : le retard reste subi, il décale la
journée, contraint les trajets suivants, et entre dans ce que l'agent raconte le soir. Il cesse
seulement de peser sur la gravité.

⚠ **Numérotation** : le ticket et le contrat de tests appellent cette décision **D7** ; ce
paragraphe disait D6, qui est déjà pris par le périmètre retiré aux tickets 059, 078 et 095.
Corrigé ici — deux numéros pour une même décision se relisent mal six mois plus tard.

### L'ablation déclarée (Q4 du ticket)

`jugement: aucun` dans la déclaration : aucun appel, `importance_estimee` vide — **jamais zéro**,
qui est la valeur d'un trajet parfait — et `importance_retenue` égale à la gravité déterministe.
C'est le bras qui mesure ce que le jugement ajoute, et c'est aussi le mode sous lequel tourne le
test en or.

### Le coût, et le chemin critique

Un appel par exposition. Sur la prise `arrivee`, l'appel est **bloquant** sur le traitement de
l'observation ; les exposés sont rares par construction (quatre applications au run du 19/09).
L'appel passe par la file et la contre-pression ordinaires — aucune file à part, aucun délai de
repli, aucune valeur par défaut en cas de pénurie. Le temps d'attente est journalisé par
exposition et agrégé à la bascule de journée. Voir Q6.

---

## 6. Lot 4 — le foyer, indifférent au canal

Le seul lot lourd, le seul qui touche un prompt, derrière `memoire__partage_foyer_enabled`, **faux
par défaut**.

### Fichiers

| Fichier | Nature |
|---|---|
| `services/llm-agents/llm/foyer.py` | **neuf** — `recit_du_soir()`, `croyances_partagees()`, repère de lecture |
| `agents/llm_agent.py` | le bloc entre dans le contexte de `stm_reflection` ; `SCHEMA_REFLEXION_VERSION → 4` |
| `packages/mobility_llm/.../stm_reflection/{template.md.j2,output_schema.json}` | champ de provenance par concept |
| `settings.py` | quatre réglages (ci-dessous) |
| `urban_mobility_agents/simulation_controller.py` | le repère de lecture au point de reprise de 3 h |
| `tests/test_100_lot4_foyer.py` | **neuf** |

### Ce qui circule, et comment un seul saut tient

| Ce qui circule | Règle | Un seul saut |
|---|---|---|
| **Le récit du soir** — tous les épisodes de la journée de chaque autre membre présent, lecture du matin comprise (D1) | un énoncé par déplacement, plus un par événement déposé ; source nommée avec son âge ; bloc borné, troncature comptée et alarmée | **structurel** : un récit n'est jamais écrit dans la mémoire du receveur, il n'existe que dans l'appel. Il n'y a rien à re-raconter |
| **Les croyances** — R1 à R6 du 078, inchangées | ancrage `observations ≥ 1`, jamais montré deux fois, axe renseigné, mode praticable, borne, membre présent | **par la provenance** : une croyance née d'un ouï-dire porte `origine: entendu` et n'est jamais candidate au partage, même confirmée plus tard (Q2) |

### Le champ de provenance dans le schéma de réflexion

Le 078 § 4.1 refusait explicitement ce champ. D2 l'impose, et il n'y a pas de raccourci : sans lui,
un concept né d'un ouï-dire est indiscernable d'un concept né d'un trajet.

```json
"source": {
  "type": "string",
  "enum": ["lived", "heard"],
  "description": "Whether this comes from your own day, or from something you were told at home"
}
```

Obligatoire (`required`), `additionalProperties: false` oblige. Traduit en `origine: vecu |
entendu` à l'écriture. **`SCHEMA_REFLEXION_VERSION` passe à 4** (V5) : le cache de réflexions
accumulé sous la version 3 est perdu, et c'est le comportement voulu — une réponse sans provenance
servie telle quelle ferait passer tout ouï-dire pour du vécu.

⚠ Quand le drapeau est **éteint**, aucun bloc de foyer n'entre dans l'appel, mais le champ est
quand même demandé et vaut `lived` partout. C'est ce qui garde la version de schéma unique entre
les deux bras, donc comparable.

### Les réglages

| Réglage | Défaut | Rôle |
|---|---|---|
| `memoire__partage_foyer_enabled` | `false` | l'interrupteur |
| `memoire__partage_foyer_observations_min` | `1` | R1 ; `0` est le bras « ouï-dire » de robustesse |
| `memoire__partage_foyer_max_bloc` | `12` | R5, garde-fou sur les croyances |
| `memoire__recit_soir_max` | `8` | borne du récit du soir (Q1), tri par gravité décroissante puis par heure |

### Ce que la première mesure regarde, avant tout le reste

Le nombre d'énoncés servis par soir et le nombre de troncatures. Le 077 a mesuré un prompt de
consolidation qui stagne vers 2 100 jetons ; D1 y ajoute la journée entière de chaque autre
membre, ce qui est la seule addition du ticket dont le volume ne soit pas borné par une règle
d'ancrage. Si ce chiffre dérive, c'est là que ça se verra.

---

## 7. Lot 5 — sorties et mesure, communes aux deux canaux

| Sortie | Ce qui change |
|---|---|
| `evenements.jsonl` | remplace `chocs.jsonl` ; une ligne par application, avec `canal`, `moment`, `role`, `importance_estimee`, `valence`, `modes_touches`, `importance_retenue`, `doc_id` |
| `moves.csv` | `Choc` → `Événement`, `Jour relatif au choc` → `Jour relatif à l'événement`, plus `Rôle` (`expose \| co_resident \| temoin`) et `Raison d'exposition`. `Contrainte de chaîne` existe déjà (V11) |
| `agent_memory_events.jsonl` | `origine` sur chaque entrée et chaque croyance ; le récit du soir servi, ligne par ligne |
| `mesures/evenement_par_jour.csv` | remplace `choc_par_jour.csv` ; **une** fonction pour les deux canaux |
| `scripts/analysis/figure_evenement.py` | **une** figure, décrochage et retour par rôle ; la figure 7.2 en devient la première instance |
| tableau des quatre voies | même recherche du texte dans `llm_exchanges.jsonl` et `trace_rappel.jsonl`, par régime et par rôle |

**Le renommage de colonnes a quatre lecteurs** : `scripts/analysis/mesures/calcul.py`,
`scripts/analysis/archives_moves.py`, `scripts/analysis/memoire/choc.py`, et les notebooks. Tous
lisent par **nom** de colonne : la lecture accepte les deux graphies pendant une version, en
journalisant laquelle elle a trouvée. Un run archivé doit rester dépouillable.

**Les quatre règles du 093 s'appliquent sans exception** : journée à 3 h, « la veille » est le jour
vécu précédent, une cellule vide n'est pas un zéro, les jours relatifs se redérivent des
horodatages.

**Garde de vacuité.** Un rôle sans effectif sort « non concluant », jamais 0,0. L'appariement du
souvenir au texte injecté échoue déjà (mesuré le 2026-09-16 : le vécu est **reformulé** par la
réflexion) — la colonne reste **vide**, jamais `faux`.

---

## 8. Lot 6 — leviers, documentation, changelog

| Chantier | Détail |
|---|---|
| `make run EVENEMENT=<nom>` | sur le modèle exact de `CHOC=` (`make/gama.mk:85-96`), `EVENEMENTS_DIR = services/llm-agents/config/evenements` |
| `CHOC=` et `PRESSE=` | alias qui écrivent la même clé, avec un message disant lequel a servi |
| passe-plat compose | montage du corpus (fait au lot 2), variables d'environnement |
| `experiences/experience.py` | le refus E6 est levé **pour les deux** types (V12) |
| `llm/chocs.py` | **supprimé**, après un run court de non-régression sur c6 |
| `docs/arch/evenements.md` | remplace `chocs-declares.md` ; le fichier d'origine devient un renvoi d'une ligne |
| `docs/arch/memory-stm-ltm.md` | le champ `origine` et le récit du soir |
| `docs/arch/mesures-personas.md` | `evenement_par_jour.csv` |
| `docs/changelog.md` | une entrée par lot livré, en tête |

---

## 9. Ce que ce plan ne fait pas

- Il ne lance **aucun run** et ne demande aucune campagne. Les runs P0/P1 du 059 restent après.
- Il ne touche **aucune règle de mémoire** hors de ce qui est listé : ni seuil de choc, ni force,
  ni viviers, ni durée de service. Le déplacement du seuil à 0,66 (095 Q3bis) reste au 095.
- Il ne dégrade **aucune offre** : un `canal: lu` ne touche ni OTP, ni GTFS, ni OSMnx.
- Il n'ouvre **aucun second saut**. Aucun paramètre du plan ne rétablit la rétro-information.
- Il n'écrit **rien** dans `docs/paper/article/`. Le chapitre alternatif reste sous verrou, et le
  signalement d'impact se rend à chaque lot livré, sans correction.
