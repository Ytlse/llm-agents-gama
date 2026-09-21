# Ticket 096 — Jev (TypeSafe) : une troisième famille de décideur, ni LLM ni tabulaire

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-21, rien n'est lancé.
>
> **Tout ce que ce ticket affirme du comportement de Jev est lu dans sa documentation**
> (`https://docs.typesafe.ai/`, pages `introduction`, `primitives/choice`, `models`, `api`,
> `confidence`, `model-jaggedness/jev-1.13`, `introduction/quickstart`, consultées le
> 2026-09-21). **Aucun appel n'a été passé.** Le lot 0 existe pour transformer ces lectures en
> mesures avant qu'une ligne n'entre dans `services/`.

---

## 1. La question, en une phrase

Le chapitre 6 oppose treize décideurs en deux blocs : des **agents LLM zéro-shot**, qui ne
connaissent rien de l'enquête locale et raisonnent en texte, et des **méthodes tabulaires
supervisées**, entraînées sur l'enquête et qui rendent des probabilités calibrées. Jev occupe
une case vide entre les deux : **zéro-shot comme les premiers, discriminatif et calibré comme
les seconds**.

- Jev proche de la bande tabulaire → ce n'est pas le jeu de rôle génératif qui achète la
  performance, c'est la connaissance du monde mise en forme probabiliste.
- Jev près des bras LLM ou en dessous → l'incarnation et le raisonnement verbalisé portent
  quelque chose qu'un classifieur typé ne capture pas.

Les deux réponses sont publiables. C'est ce qui fait la valeur du bras : **il n'a pas de
résultat décevant**.

Ce n'est **pas** un remplaçant des modèles tabulaires. Eux portent l'information de l'enquête
locale et tiennent le rôle de plafond informé ; Jev n'a rien vu de Toulouse. Les substituer
l'un à l'autre effacerait la seule référence entraînée du chapitre.

---

## 2. Ce qu'est Jev, en quatre lignes

Un **classifieur zéro-shot à sortie typée**. On envoie un `state` (texte) et des questions
typées — `Choice` (une option parmi un ensemble), `Score` (2 à 10 niveaux), `Noul` (vrai/faux
en probabilité) — et on récupère un choix, **la distribution complète sur les options**, et une
confiance. Pas de génération de texte : `jev-1.13.0` n'est pas entraîné pour ça.

| | |
|---|---|
| Modèle | `jev-1.13.0` (alias `jev-latest`, `jev-preview`) |
| Endpoint | `POST https://api.typesafe.ai/v1/systemone`, bearer token |
| Contexte | 64 000 jetons/requête, dont 32 000 pour `state` + la plus longue question |
| `Choice` | 255 options maximum, probabilités sommant à 1, plus une confiance |
| Tarif | 0,042 $/M jetons **d'entrée** ; sortie gratuite |
| Débit annoncé | 1 200 req/min, 250 k jetons/s — « ajustés dynamiquement, sans préavis » |
| Langue | anglais en premier ; le nôtre l'est depuis le ticket 074 |
| Hébergement | distant uniquement, pas de self-hosting documenté |
| Graine / température | **non documentées** — le déterminisme est inconnu |

---

## 3. Pourquoi ça s'insère sans rien forcer

`itinary_multi_agent` demande aujourd'hui : *voici un persona, voici 4 à 6 itinéraires indexés,
rends une probabilité par option sommant à 100*. C'est **littéralement** un `Choice`. Les
`probabilities` de Jev remplacent `poids_presentes` sans conversion, et le tirage graîné
(`graine_tirage`) ne bouge pas.

La plateforme est bâtie pour ça : `experiences/decideurs.py` expose un contrat unique
`choisir(person, ctx, presentees)`, sept implémentations l'honorent, `runner.py` rejoue un jeu
gelé sans simulateur. `decideur_antigravity.py` (498 lignes) est le précédent d'un décideur qui
**ne passe pas par la passerelle**.

Mesuré sur `exp_gemini-35-fl_proexp05_…_EN_c/executions/2026-09-16_22_20_25` (3 299 décisions) :

| | |
|---|---:|
| Sollicitations réelles (hors `choix_unique`) | 2 482 |
| Options par décision — moyenne / médiane / max | 4,19 / 5 / **6** |
| Payload par décision — moyenne / max (caractères) | 1 561 / 3 679 |

Six options contre un plafond de 255, 3,7 ko contre 32 000 jetons de `state`. Aucune contrainte
de la plateforme n'approche les limites de Jev.

---

## 4. Ce qui ne passe pas, et qu'il faut dire avant de commencer

| Chaîne actuelle | Sur Jev |
|---|---|
| Distribution sur les options | ✅ natif, plus la confiance |
| `reason` / `raison` par option | ❌ pas de génération de texte |
| STM / LTM, `souvenirs`, perception filter | ❌ ces catégories produisent du texte — **le bras est sans mémoire par construction** |
| Prompt système calibré (3 942 car., arbitrage en 4 étapes) | ⚠️ surface différente : `instructions` + descriptions d'options |
| Lots multi-personas par appel | ⚠️ un `state` par requête ; sans objet, le runner décide déjà une décision à la fois |

Et le point qui doit tenir la prudence : **la page de limitations de Jev cite les nombres, les
durées, les comparaisons temporelles et le raisonnement multi-sauts comme ses faiblesses
connues**, ainsi que la chute d'exactitude quand le `state` grossit de contenu hors sujet. Nos
options sont décrites par des durées, des distances et des heures, et le prompt expert est un
arbitrage en quatre étapes. C'est exactement là que ça peut casser. Aucune hypothèse favorable
n'est posée : le lot 0 tranche.

---

## 5. Le code envoyé à l'API

### 5.1 La règle de construction

| Ce qu'on envoie | D'où ça vient |
|---|---|
| `state` | **Le bloc persona rendu par `template.md.j2`, à l'identique** : perception, contexte météo, `day_outlook`, agenda, options indexées. C'est la condition de comparabilité — à texte présenté égal. |
| `instructions` | Le `content` de la variante `prompts.yaml`, **amputé de son bloc `[Output instructions]` et du schéma JSON** : le type `Choice` les remplace. |
| `criteria` | Une entrée par option présentée, clé `option_<index>` dans l'**ordre de présentation** (`ordre_presentation`, graine `graine_ordre`). |
| `model` | `jev-1.13.0`, **jamais** `jev-latest` (§ 6.2). |

Les clés sont indexées et non nommées par mode : deux options partagent souvent le même mode
(deux itinéraires bus, deux itinéraires à pied dans l'exemple ci-dessous) et un dictionnaire les
écraserait l'une l'autre.

L'amputation du bloc de sortie est un **écart assumé** : le bras ne joue pas `prompt_expert_16`
mais sa partie arbitrage. L'empreinte scelle le sha du texte réellement envoyé, pas le nom de la
variante — sans quoi l'exécution s'annoncerait sous un prompt qu'elle n'a pas joué.

### 5.2 L'appel, sur une décision réelle du jeu gelé

Persona 16127 (Renée), activité `7e5b4f97-…c001`, motif `shop`, six options.

```python
import os
from typesafe_sdk import Choice, TypeSafeClient   # pip install typesafe-sdk (Python >= 3.10)

# Le SDK lit TYPESAFE_API_KEY tout seul ; le dépôt nomme ses clés autrement,
# on la passe donc explicitement (cf. § 6.3).
client = TypeSafeClient(api_key=os.environ["PROVIDER_KEYS__typesafeAI"])

INSTRUCTIONS = (                       # str — prompt_expert_16, bloc d'arbitrage seul
    "You will sequentially embody people living in Toulouse. Your task is to select the "
    "optimal travel mode. The assessment must be purely algorithmic and proceed in 4 steps:\n"
    "1) Strict filtering: Define the persona's non-negotiable red lines so as to rule out "
    "invalid options from the outset.\n"
    "2) Cost matrix: Compute the true opportunity cost of each option by weighting the "
    "following variables exclusively according to the profile's attributes (age, income, "
    "health): time saved VS comfort; raw access friction; safety filter; reality filter; "
    "comfort filter; chain of the day.\n"
    "3) Sustainability: Apply the 48-hour rule to assess the viability of the physical or "
    "financial effort."
)

STATE = """\
Renée, 29, Full-Time Worker (household of 3, high income). Usual trip purposes: Shopping. Lives in: 1st ring
Destination: shop | Departure: 09:28
Context: Weather: 10°C, Clear/Sunny. Today 9°C to 17°C, sunrise 08:15, sunset 17:18. No precipitation expected.
Weather later: afternoon 12°C, Clear/Sunny · evening 13°C, Clear/Sunny
Further trips planned today: (none)"""

CRITERIA = {                           # dict[str, str] — 255 entrées maximum
    "option_0": (
        "Mode foot,bus,foot,bus,foot. Travel time: 2 hours, 8 minutes, including 48 minutes "
        "of walking. Has no public transport pass. Walk to 'AUSSONNE - République': 9 min; "
        "Bus '362' to 'TOULOUSE - Gutenberg': 46 min; Walk to 'La Vache': 29 min; "
        "Bus 'L10' to 'Fenouillet Ctre Cial - Entrée Nord': 25 min; Walk to 'shop': 9 min. "
        "Total distance 37.7 km."
    ),
    "option_1": "Mode car. Estimated duration: 19 minutes. Distance: 10.0 km.",
    "option_2": "Mode foot. Estimated duration: 2 hours. Distance: 9.9 km.",
    "option_3": (
        "Mode foot,bus,foot,bus,foot,bus,bus,foot. Travel time: 2 hours, 7 minutes, including "
        "19 minutes of walking. Has no public transport pass. Three transfers. "
        "Total distance 31.0 km."
    ),
    "option_4": (
        "Mode foot. Travel time: 2 hours, 7 minutes, including 2 hours, 7 minutes of walking. "
        "Total distance 10.0 km."
    ),
    "option_5": (
        "Mode foot,bus,foot,bus,bus,foot. Travel time: 1 hour, 56 minutes, including 19 minutes "
        "of walking. Has no public transport pass. Total distance 37.7 km."
    ),
}

reponse = client.system_one(
    model="jev-1.13.0",                                    # str, version FIGÉE
    state=STATE,                                           # str
    questions={                                            # dict[str, Question]
        "mode": Choice(
            instructions=INSTRUCTIONS,                     # str
            criteria=CRITERIA,                             # dict[str, str]
        ),
    },
)
```

### 5.3 La sortie attendue

`reponse.answers["mode"]` porte trois champs : `choice: str`, `probabilities: dict[str, float]`
sommant à 1, `confidence: float` entre 0 et 1. `reponse.usage` porte `input_tokens` et
`output_tokens`.

```jsonc
// ILLUSTRATIF — la forme est celle de la documentation, les valeurs ne sont pas mesurées.
{
  "model": "jev-1.13.0",
  "answers": {
    "mode": {
      "type": "choice",
      "choice": "option_1",
      "probabilities": {
        "option_0": 0.04,
        "option_1": 0.71,
        "option_2": 0.02,
        "option_3": 0.03,
        "option_4": 0.02,
        "option_5": 0.18
      },
      "confidence": 0.65
    }
  },
  "usage": { "input_tokens": 1102, "output_tokens": 0 }
}
```

### 5.4 La conversion en `ReponseDecideur`

Rien d'inventé : c'est le chemin de `DecideurModele`, la prédiction remplacée par l'appel.

```python
poids = [proba[f"option_{i}"] for i in range(len(presentees))]   # ordre de présentation
idx   = self._tirer(poids, graine_ordre(ctx.graine_tirage, person.person_id, ctx.activity_id))
return ReponseDecideur(
    index=idx,
    fournisseur="typesafe:jev-1.13.0",
    distribution=_distribution(poids, presentees),   # agrégation par mode canonique
    poids=poids,
    reponse_brute=json.dumps({"probabilities": proba, "confidence": conf,
                              "input_tokens": usage.input_tokens}, ensure_ascii=False),
    raison="",                                       # Jev ne rédige pas — champ vide, pas comblé
    presente=_presente_local(presentees),
)
```

Sur l'exemple, `_tirer` appliqué à ces poids illustratifs avec la graine réelle de la décision
(`graine_ordre(42, "16127", "7e5b4f97-…c001")` = 9 932 238 118 146 211 744, tirage r = 0,295)
rend l'index **1** — la voiture, celle que `gemini-3.5-flash-lite` sous prompt expert avait
choisie à 1,00. Le calcul est vérifié ; ce sont les probabilités qui sont supposées, pas le
tirage. **La confiance est
archivée sans être utilisée** : elle n'entre dans aucune décision tant que personne n'a montré
ce qu'elle vaut ici.

`raison` reste **vide**, jamais remplie d'un texte fabriqué à partir des probabilités : une
justification synthétisée se lirait comme une sortie de modèle dans les traces et dans les
rapports mémoire.

---

## 6. Les trois décisions déjà prises

### 6.1 Les deux prompts, minimal et expert

Le bras se joue en deux variantes, **celles du § 6.1 et aucune autre** : `prompt_minimal_02` et
`prompt_expert_05`, chacune amputée de son bloc de sortie. Décision de l'auteur du 2026-09-21,
après qu'une première exécution est partie sur `prompt_expert_16`, la variante *active* du
dépôt : c'est `prompt_expert_05` que le chapitre 6 mesure, et un bras comparé à une table doit
porter la consigne de cette table. Sans les deux, la figure 6.2 — ce que
l'ingénierie de prompt déplace — n'a rien à dire de Jev, et c'est précisément la mesure
intéressante : **un classifieur typé a-t-il la même sensibilité à la consigne qu'un modèle
génératif ?** L'ordre reste minimal d'abord : s'il s'effondre, l'expert dira si c'est la
consigne ou le substrat.

### 6.2 La version est figée : `jev-1.13.0`

`jev-latest` rendrait l'empreinte mensongère au premier changement de version, en silence. Le
lot 1 **refuse** un alias dans `DecideurSpec.modele` plutôt que de le résoudre : un alias résolu
au lancement scelle une version que l'`experience.yaml` ne porte pas.

Corollaire, à traiter dans le même lot : le service est jeune (1.13, page de limitations
publiée, débits « ajustés sans préavis »), distant, et sans repli local. Le bras peut devenir
irrejouable avant AAMAS 2027. La parade existe déjà — `reponse_brute` est archivée, donc
`DecideurRejeu` conserve le bras même si le service disparaît. Elle ne vaut que si le lot 1
archive **la réponse entière**, probabilités et confiance comprises, et pas seulement l'index.

### 6.3 La clé : `PROVIDER_KEYS__typesafeAI`

Convention du dépôt (`PROVIDER_KEYS__<instance>`), pas celle du SDK (`TYPESAFE_API_KEY`). Le
décideur lit la variable du dépôt et passe `api_key=` explicitement ; il ne laisse pas le SDK
résoudre la sienne, sans quoi une clé oubliée dans l'environnement servirait à l'insu de
l'empreinte.

**Le décideur ne passe pas par `llm_gateway`**, et c'est délibéré : la passerelle est construite
autour de complétions de chat avec schéma JSON, lots multi-agents et rotation de quotas. Jev n'a
ni chat, ni schéma, ni besoin de rotation (1 200 req/min pour 2 482 décisions). L'y faire entrer
demanderait de simuler une interface de chat par-dessus une API qui n'en est pas une.
`decideur_antigravity.py` a déjà tranché ce cas dans le même sens. Réversible si la charge
change.

---

## 7. Les lots

### Lot 0 — la sonde (≈ 2 h, hors plateforme, jetable)

Script dans le scratchpad, **aucune ligne dans `services/`**. 200 décisions relues depuis
`data/jeux/population_1000_AAMAS_v6_20260316_EN_c/propositions.jsonl`, un `Choice` par décision.

Ce qu'il rend, et qui décide de la suite :

| Mesure | Seuil de passage |
|---|---|
| **Déterminisme** : 3 passes identiques, même `state`, même `criteria` | divergence d'index rapportée telle quelle ; si > 5 %, le bras se déclare stochastique et le lot 2 joue plusieurs graines |
| Taux de réponse exploitable (6 clés rendues sur 6 demandées, somme à 1) | ≥ 99 % |
| Biais de position : mêmes options, ordre permuté sur 50 décisions | écart de distribution rapporté, sans seuil — c'est une mesure, pas un filtre |
| Latence par appel, jetons d'entrée réels, coût extrapolé | pour dimensionner le lot 2 |
| Composite EMD–JSD grossier sur les 200 | aucun seuil : un composite pire que le tout-voiture (30,73) n'annule pas le bras, il le rend intéressant autrement |

Le déterminisme et le biais de position sont les deux inconnues que la documentation ne couvre
pas. Elles ne se devinent pas.

**Go/no-go explicite** avant le lot 1. Un no-go se solde par une note dans ce ticket, pas par du
code mort.

### Lot 0 — RÉSULTATS (passé le 2026-09-21) — **GO**

> ⚠ **DEUX CONCLUSIONS DE CETTE SECTION SONT FAUSSES, et le lot 2 les a renversées.** La sonde
> a joué `prompt_expert_16`, la variante *active* du dépôt ; le bras mesuré joue
> `prompt_expert_05`, celle du § 6.1. Sous cette consigne-là, Jev fait **4,19** de composite et
> non « la région des planchers », et la consigne le déplace de **9,56 points** au lieu de
> « rien ». Ce qui reste vrai : le déterminisme, l'absence de biais de position, l'exploitabilité,
> les coûts, et le fait que Jev n'écarte jamais tranchément. Les passages caducs sont barrés
> ci-dessous plutôt que réécrits — une sonde qui s'est trompée est une information sur la sonde.


850 appels, 30 secondes, 0,038 $. 200 décisions tirées à la graine 2026 parmi les 2 482
sollicitations de `…_EN_c/executions/2026-09-16_22_20_25`, texte présenté reconstruit à
l'identique depuis `presente.payload`. Trois passes identiques sous `prompt_expert_16`, une
passe sous `prompt_minimal_02`, une passe à ordre inversé sur 50 décisions. Sonde jetable, rien
dans `services/`.

**Exploitabilité : 100 %.** Zéro erreur, zéro clé manquante, zéro réponse tronquée. Dix réponses
somment à 0,99 ou 1,01 : **Jev arrondit ses probabilités à deux décimales**, et une tolérance de
1e-6 les comptait à tort en échec. La tolérance du lot 1 est 0,02, et les poids sont
renormalisés avant `_tirer`.

**Déterminisme : quasi, pas exactement.** Écart par option entre deux appels identiques : 0,013
en moyenne, 0,08 au maximum. L'option élue change sur 11 décisions de 200 (5,5 %), et
**uniquement sur des quasi-égalités** — écart 1ᵉʳ-2ᵉ de 0,04 chez les divergentes contre 0,49
chez les stables. Comme la plateforme **tire** dans la distribution au lieu de prendre l'argmax,
la grandeur qui compte est le bruit de 0,013, pas le basculement d'index. Le bras n'est pas
déclaré stochastique pour autant : le lot 2 joue les graines du ticket 073 comme les autres.

**Sensibilité à l'ordre : réelle, mais sans biais de position.** Ordre d'insertion inversé, noms
de clés inchangés : l'écart moyen par option passe de 0,013 à 0,072, soit **5,5 fois le bruit
d'appel**. Et pourtant aucune primauté ni récence — `option_0` reçoit 0,259 de masse moyenne
insérée en premier, 0,258 insérée en dernier. L'ordre **perturbe la décision individuelle sans
déplacer l'agrégat**. Conséquence pratique : `ordre_presentation` étant graîné, une exécution
donnée reste reproductible ; c'est la dispersion inter-graines qui s'en trouve gonflée, et c'est
exactement ce que le ticket 073 mesure.

**Ce que Jev préfère, et c'est là que ça se joue.** Sur les mêmes 200 décisions et la même offre
que le bras archivé :

| | options | masse Jev/option | masse gemini-3.5 expert/option |
|---|---:|---:|---:|
| voiture | 143 | 0,567 | **0,691** |
| transports collectifs | 556 | **0,132** | 0,071 |
| marche | 308 | 0,127 | 0,164 |
| vélo | 74 | 0,082 | 0,151 |

La dilution (2,93 options TC en moyenne contre 1,00 voiture) frappe les deux décideurs de la
même façon : ce qui est isolé ici est bien une préférence. **Jev ne filtre pas.** Sa probabilité
maximale médiane est 0,64 contre 0,80 au bras LLM, il ne sature (=1) que 1 % du temps contre
31 %, et il n'attribue **jamais** zéro à l'option voiture là où le LLM le fait 12,6 % du temps.
L'étape « filtrage strict » du prompt expert ne prend pas.

| Parts modales, masse de probabilité, 200 décisions | marche | vélo | TC | voiture | L1 |
|---|---:|---:|---:|---:|---:|
| EMC² (cible) | 26,80 | 4,12 | 12,37 | 56,70 | — |
| gemini-3.5 expert (archivé) | 25,28 | 5,58 | 19,72 | 49,43 | **17,59** |
| Jev, prompt expert | 19,58 | 3,02 | 36,86 | 40,54 | 48,99 |
| Jev, prompt minimal | 21,83 | 7,31 | 33,92 | 36,95 | 49,46 |

**Ces L1 ne sont PAS comparables au 13,85 du § 6.1** : 200 décisions sur 3 299, choix uniques
exclus, masse de probabilité et non tirage. ~~La ligne gemini est là pour donner l'étalon sur ce
support-là, et elle seule autorise la lecture : Jev est à près de trois fois la distance du bras
LLM, dans la région des planchers du § 6.1 plutôt que dans celle des bras LLM.~~ **CADUC** : ces
deux L1 sont ceux de `minimal_02` et `expert_16`. Le lot 2 mesure `expert_05` à 12,59, devant
le bras gemini. La sonde n'avait pas essayé la bonne consigne.

**Ce n'est pas un défaut de mise en forme.** Contre-épreuve passée dans la foulée : descriptions
d'options resserrées à la durée et la distance, sans le détail des correspondances — le cas que
la documentation de Jev désigne comme son point faible (« large, irrelevant state »). Le L1
passe de 48,99 à 44,85 et la masse voiture par option de 0,567 à 0,597. Réel, faible, et loin de
refermer l'écart. ~~La consigne ne le referme pas non plus : minimal et expert rendent 49,46 et
48,99, quand le même passage coûte 9 points au bras gemini au § 6.2.~~ **CADUC, et c'est
l'erreur de raisonnement à retenir** : de deux consignes qui échouent, la sonde a conclu que la
consigne ne pouvait rien. `prompt_expert_05` en déplace 9,56 points (§ lot 2). Deux points ne
font pas une droite.

**Accord d'argmax avec le bras archivé** : 75,5 % (expert), 73,5 % (minimal) sur le mode
canonique.

**Latence et coût confirmés** : 274 ms de médiane à 8 fils, 1 099 jetons d'entrée médians. Le
rejeu complet du jeu AAMAS v6 tient en 0,12 $ pour une variante, 0,24 $ pour les deux, 1,21 $
pour `enquete_058_test` — les extrapolations du § 8 sont vérifiées, pas estimées.

**Verdict : GO.** ~~Le résultat attendu du lot 2 est désormais orienté : Jev ne viendra pas au
contact de la bande tabulaire.~~ **CADUC** — il y vient (4,19 contre 3,60–4,09). L'anticipation
était tirée d'une sonde à 200 décisions sous la mauvaise consigne, et elle n'aurait pas dû être
écrite : le lot 0 avait pour mandat de dire si le bras était mesurable, pas de préjuger de sa
mesure.

Brut conservé hors dépôt : `<scratchpad>/lot0/{sonde.py,analyse.py,brut.jsonl,entree.json}`.

---

### Lot 1 — le décideur (≈ 1 j)

- `services/llm-agents/experiences/decideur_typesafe.py`, calqué sur `decideur_modele.py`
  (`_tirer`, `_distribution`, `_presente_local` réutilisés, pas réécrits).
- `DecideurSpec.type` : littéral `typesafe` ; `modele` obligatoire et **refusé s'il est un
  alias** ; `parametres` porte le nom de la variante de prompt.
- `nommage.py` : abréviation `jev` dans `ABREV_DECIDEUR`, suffixe de variante comme les bras
  LLM (`promin02` / `proexp05`).
- Empreinte : `jev-1.13.0` **et** le sha256 du texte `instructions` réellement envoyé.
- Non-décision explicite (`non_imputable`) sur échec, quota ou réponse incomplète — **jamais**
  de repli silencieux vers un mode, ni de repli uniforme déguisé.
- `services/llm-agents/tests/test_096_typesafe.py`, un test par règle, contrat écrit avant le
  code dans `specs/ticket_096/tests.md`.

### Lot 1 — LIVRÉ le 2026-09-21

Contrat écrit avant le code : [`specs/ticket_096/tests.md`](../../specs/ticket_096/tests.md),
28 règles. **45 tests passent**, `services/llm-agents/tests/test_096_typesafe.py`.

Ce qui est en place :

| | |
|---|---|
| `experiences/decideur_typesafe.py` | `DecideurTypesafe`, au contrat commun, calqué sur `decideur_modele.py` |
| `DecideurSpec.type` | littéral `typesafe` ; `modele` obligatoire et **alias refusé à la validation** |
| `nommage.py` | nommé par sa version (`jev-1130`), variante de prompt dans le nom, **pas de segment de température** |
| Empreinte | `type`, `modele`, `variante` et `instructions_sha256` — le sha du texte **amputé**, celui qui part vraiment |
| `requirements.txt` | `typesafe-sdk==0.7.0`, épinglé pour la même raison que le modèle |
| Dashboard | le type apparaît au formulaire, glosé « Jev (TypeSafe) — classifieur typé, sans quota » |

Les noms composés sont ceux qu'on attendait, parallèles aux bras LLM :
`exp_jev-1130_proexp05_…_EN_c_nosim` et `exp_jev-1130_promin02_…_EN_c_nosim`.

**Une décision de conception qui n'était pas dans le plan.** Le ticket annonçait la variante de
prompt dans `decideur.parametres` ; elle vit en fait dans `gabarit.variante`, où la plateforme
la range déjà pour les bras LLM et où `empreinte_gabarit` va la chercher. La suivre coûtait
moins que la dupliquer, et évite deux sources de vérité pour une même information.

**Le contrat a été éprouvé par mutation**, parce qu'un test qui passe ne prouve pas qu'il
mesure. Quatre altérations volontaires du décideur, pour voir lesquelles les tests attrapent :

| Altération | Attrapée par |
|---|---|
| l'amputation du bloc de sortie est retirée | C3, T4 |
| la tolérance d'arrondi passe de 0,02 à 1,0 | R3, R3b, E4 |
| une `raison` est fabriquée à partir des probabilités | R7 |
| `graine_tirage` est confondue avec `graine_ordre` | **personne** — puis R6, corrigé |

La quatrième est le motif habituel : les deux graines valent 42 par défaut, donc les confondre
ne changeait rien dans le test et R6 passait pour la mauvaise raison. Le test pose désormais
deux graines distinctes, et l'altération tombe. C'est la seule des quatre qui aurait pu partir
en production.

**Fumée bout-en-bout contre l'API réelle** (vrai client, vrai `prompt_manager`, vraie
conversion) : empreinte `instructions_sha256 = d529aca8…`, 1 662 caractères servis en
`instructions`, 758 jetons d'entrée, poids convertis et renormalisés, `distribution` agrégée par
mode canonique, `raison` vide, réponse entière archivée.

Ce qui n'est **pas** fait, et qui n'est pas de ce lot : aucune exécution n'a été lancée, aucun
score calculé, aucune figure de l'article touchée.

---

### Lot 2 — le rejeu (≈ 0,5 j de travail, quelques minutes de machine)

Les deux variantes de prompt sur `population_1000_AAMAS_v6_20260316_EN_c` (3 299 décisions),
**et rien d'autre**. Le jeu `enquete_058_test_20260316` est **hors périmètre** : décision de
l'auteur du 2026-09-21, aucune mesure supplémentaire. Scores par la formule
`v1_reference` et le référentiel EMC² déjà scellés — aucun scoreur à toucher. Figure regénérée
(mémoire : toute analyse d'expérience se livre avec sa figure).

### Lot 2 — LIVRÉ le 2026-09-21

Deux bras, un seul jeu — `population_1000_AAMAS_v6_20260316_EN_c`, celui du § 6.1. Scoreur,
formule `v1_reference` et référentiel EMC² inchangés : aucune ligne du scoreur n'a été touchée.
3 154 décisions comptées sur 3 161 exploitables pour chacun, **zéro erreur**, zéro non-décision.

| Décideur | Composite EMD–JSD | Hors choix unique | L1 parts globales |
|---|---:|---:|---:|
| Gradient boosté (LightGBM) | **3,60** | 5,84 | 9,49 |
| Régression logistique à noyau | 3,61 | **5,61** | 6,69 |
| Logit multinomial | 4,02 | 6,63 | 8,99 |
| Forêt aléatoire | 4,09 | 5,81 | **5,28** |
| **Jev 1.13, `prompt_expert_05`** | **4,19** | 7,25 | 12,59 |
| Prompt expert, `gemini-3.5-flash-lite` | 4,86 | 6,86 | 13,85 |
| … | | | |
| **Jev 1.13, `prompt_minimal_02`** | **13,75** | 19,84 | 42,76 |

Parts obtenues sous `expert_05` : marche 32,23 (cible 26,80), voiture 51,85 (56,70), TC 10,92
(12,37), vélo 4,99 (4,12).

**Jev arrive au contact de la bande tabulaire** — 4,19 contre 3,60 à 4,09 — et **devance le
meilleur bras LLM** (4,86).

**L'estimation appariée le confirme** (bootstrap du 2026-09-21, `docs/traces/2026-09-21_ticket096_lot2/`,
même script et même méthode que la trace du 2026-09-17 : 2 000 réplicats, graine 2026, grappe au
niveau de la personne, 868 personnes communes aux onze bras). **Jev sous prompt expert n'est
séparable d'AUCUNE des quatre méthodes tabulaires** : +0,66 [−0,63 ; +2,07] face au gradient
boosté, +0,69 [−0,57 ; +2,06] face à la régression à noyau, +0,27 [−1,11 ; +1,70] face au logit
multinomial, +0,25 [−1,03 ; +1,61] face à la forêt aléatoire. `gemini-3.5` sous la même consigne,
lui, **est** séparable des deux premières (+1,35 et +1,38, zéro exclu). Jev le devance de 0,69
point, −0,69 [−2,04 ; +0,65], sans que cet écart exclue zéro.

Gain de consigne apparié : **+9,71 [+7,80 ; +11,66]** de composite, +12,78 [+10,68 ; +14,86] hors
choix unique, +30,2 [+24,6 ; +36,0] sur le L1. Sept fois et demie la variation de cohorte, et
zéro exclu sur les trois lectures.

**Contrôle** : les quatorze paires d'origine, recalculées par le même passage, ressortent au
centième près (+1,35 [+0,28 ; +2,47], +5,50 [+4,19 ; +6,93], +4,07 [+2,47 ; +5,75]…). L'ajout des
deux bras n'a rien déplacé.

**Ce qui répond à la question du § 1.** La case vide est remplie par la branche favorable : un
classifieur zéro-shot, qui n'a rien vu de Toulouse et ne raisonne pas à voix haute, atteint le
niveau des méthodes entraînées sur l'enquête locale. Ce n'est donc **pas** le jeu de rôle
génératif qui achète la performance — c'est la connaissance du monde, mise en forme
probabiliste. Le résultat est d'autant plus net que Jev est le seul bras à n'avoir **aucune
mémoire** et à ne produire **aucun texte**.

**Et la consigne pèse plus sur lui que sur les modèles de langue.**

| Bras | minimal → expert | gain |
|---|---|---:|
| **Jev 1.13** | 13,75 → 4,19 | **9,56** |
| Mistral Large | 14,75 → 7,63 | 7,12 |
| Gemini 3.1 Flash-Lite | 12,38 → 8,98 | 3,40 |
| Gemini 3.5 Flash-Lite | 7,02 → 4,86 | 2,16 |

C'est l'inverse de ce qu'on attendrait d'un classifieur « insensible au prompt », et cela
qualifie **quelle sorte** de consigne il suit. Les deux variantes expertes le montrent en
creux : `prompt_expert_05` énonce des **principes d'arbitrage concrets** — friction de
rabattement, autonomie des personnes âgées, port de charges, temps du travailleur — dont trois
sur quatre désignent explicitement ce que le voyageur préfère. `prompt_expert_16` énonce une
**procédure** : « quatre étapes », « matrice de coût », « règle des 48 heures ». Mesuré sur les
mêmes décisions sollicitées, la masse que Jev accorde à une option de transport collectif passe
de 0,132 (expert_16, sonde) à **0,050** (expert_05), et celle d'une option voiture de 0,567 à
**0,642**. Un classifieur typé suit des **critères de fond** ; il ne suit pas une **méthode de
raisonnement** — ce que sa propre documentation annonçait sous « indirection ».

**Ce qui tient du lot 0** : Jev n'attribue **jamais** zéro à l'option voiture (0 fois sur 1 685
où elle est offerte), sa probabilité maximale médiane reste 0,65 et il ne sature qu'à 6 %. Il
écarte moins tranchément qu'un modèle de langue ; sous la bonne consigne, cela ne l'empêche plus
d'arriver au bon endroit.

**Un défaut de mon code du lot 1, trouvé et corrigé ici.** `choisir` est une coroutine mais
appelait le client **synchrone** du SDK : un appel HTTP bloquant dans un `async def` bloque la
boucle du runner, et les huit places de son `asyncio.Semaphore` ne servaient plus à rien.
Mesuré : 40 décisions/minute, contre ~550 après passage à `AsyncTypeSafeClient`. Le résultat
était identique, seul le temps changeait — aucune des 28 règles du contrat ne pouvait l'attraper,
elles vérifient toutes *ce qui est décidé*, jamais *comment c'est transporté*. Trois règles
ajoutées (A1–A3), 48 tests. Le rejeu complet d'un bras prend désormais **six minutes**.

Figure regénérable : `scripts/analysis/plot_ticket096_jev.py`, sortie
`docs/traces/2026-09-21_ticket096_lot2/`. Elle ne touche **pas** `plot_chapitre6.py` : y ajouter
Jev changerait `ch6_echelle` sans que le texte qui la commente bouge, et c'est une décision
d'auteur sous le verrou de l'article.

**Le jeu `enquete_058_test`, rouvert par l'auteur le 2026-09-21** après qu'il a constaté
l'absence de Jev sur les planches 6.5 et 6.6. Les deux bras y ont été joués, 12 562 décisions
chacun, aucune erreur, 9 612 et 9 614 déplacements notés par l'audit unitaire relancé sur les
onze décideurs.

**Et le résultat va contre ce que le jeu de référence laissait attendre.** Sur les journées
déclarées, Jev sous prompt expert est **neuvième des onze** à 64,3 % d'exactitude pondérée,
**sous le plancher tout-voiture** (66,7 %), et son entropie croisée de **0,655** est la plus
mauvaise de tous les décideurs qui rendent une distribution — le prompt expert à modèle de
langue fait 0,356, le gradient boosté 0,419. J'avais prédit l'inverse, en raisonnant qu'un
décideur qui étale sa masse serait favorisé sur cette grandeur : étaler ne suffit pas, encore
faut-il que la masse tombe sur le mode déclaré. Le rappel des transports collectifs dit où elle
tombe à la place — **35,0 %** contre 55,2 % au bras LLM — quand celui de la marche monte à
**63,1 %**, le meilleur hors méthodes tabulaires.

Accord par paire sur le jeu de référence, même définition que le § 6.4 : Jev expert s'accorde
avec le gradient boosté sur **72,2 %** des modes les plus probables et **71,7 %** des modes
tirés, contre 69,7 % et 61,4 % au bras LLM. Il décide donc comme les méthodes tabulaires plus
souvent que le modèle de langue, et se trompe pourtant davantage : les deux grandeurs du § 6.4
se séparent sur lui plus nettement que sur n'importe quel autre décideur. Un bras `prompt_expert_16` avait été lancé par erreur avant
cette décision ; son expérience est passée en `archivee` avec son motif, données conservées.

---

### Lot 3 — décomposition en questions atomiques (**non planifié**)

L'usage prévu par TypeSafe est de découper : des `Noul` sur les contraintes (« ce persona
possède une voiture », « la météo décourage le vélo »), puis un `Choice` final, recomposés en
Python. Cela déplacerait l'arbitrage du modèle vers notre code : **le bras cesserait d'être
comparable aux bras LLM** et devrait être déclaré hybride. À rouvrir seulement si le lot 2
montre que l'échec vient du raisonnement multi-sauts et non du substrat.

---

## 8. Coût

| | Décisions | Jetons d'entrée estimés | Coût |
|---|---:|---:|---:|
| Lot 0 (sonde, 3 passes) | 600 | ~0,7 M | < 0,05 $ |
| Jeu AAMAS v6, une variante | 2 482 | ~2,7 M | ~0,11 $ |
| Jeu AAMAS v6, deux variantes | 4 964 | ~5,4 M | ~0,23 $ |
| Jeu `enquete_058_test`, deux variantes | 25 124 | ~28 M | ~1,20 $ |

Estimation à partir des 1 561 caractères de payload moyen mesurés, plus la consigne. Un rejeu
complet tient en quelques minutes à 1 200 req/min, contre les heures de jonglage entre clés
gratuites des bras LLM. **Les rejeux multi-graines du ticket 073 deviennent quasi gratuits sur
ce bras** — ce qui ne les rend pas gratuits sur les autres.

---

## 9. Risques

| Risque | Ce qu'on fait |
|---|---|
| Jev échoue sur les durées et distances (faiblesse documentée) | le lot 0 le mesure avant tout investissement ; l'échec est un résultat |
| Non-déterminisme non documenté | mesuré au lot 0 ; s'il est réel, le bras se joue multi-graines comme les LLM |
| Biais de position sur les options | mesuré au lot 0 ; l'ordre est déjà graîné (`ordre_presentation`), donc reproductible |
| Service jeune, retrait de version | version figée, réponse entière archivée, `DecideurRejeu` conserve le bras |
| Données d'entraînement inconnues | la doc dit que Jev n'est pas entraîné sur les requêtes clients ; elle ne dit rien de ce qu'il a vu avant. **Même réserve que pour les bras LLM** — à énoncer dans l'article, pas à contourner |
| Le bras sans mémoire est pris pour un bras LLM diminué | le nommage et la fiche d'expérience disent « sans mémoire par construction » |

---

## 10. Impact sur l'article (constat — ce ticket n'écrit rien)

Le § 6.1 tient **treize** décideurs. Deux bras Jev en font quinze, et touchent la figure 6.1,
son tableau, la figure 6.2 et les différences appariées de l'annexe H. Le § 6.5 sur le
non-déterminisme gagne un cas : un décideur zéro-shot dont la variabilité se mesure dans les
mêmes termes.

Aucune de ces corrections ne se fait ici : `docs/paper/article/` est sous verrou, elles passent
par la skill `article-verrou` après le lot 2, chiffres en main.

---

## 11. Hors périmètre

- **Ne remplace aucun décideur existant.** Les quatre méthodes tabulaires et les bras LLM
  restent exactement ce qu'ils sont.
- Ne touche ni à `llm_gateway`, ni à `providers.yaml`, ni à la rotation de quotas.
- Ne touche ni au contrat des 21 variables, ni aux jeux gelés, ni au scoreur, ni à la formule.
- Ne porte pas la mémoire (STM/LTM) sur Jev : il ne génère pas de texte, la question ne se pose
  pas en l'état.
- Ne calibre pas de prompt pour Jev (`prompt_calibration` vise un prompt système de chat ; la
  surface est différente). Deux variantes transposées, pas de recuit.

---

## 12. Addendum du 2026-09-21 — le hors-périmètre « ne calibre pas de prompt pour Jev » a été levé

Le § 11 excluait explicitement de régler un prompt pour Jev. **Cette ligne a été franchie le
jour même, à la demande de l'auteur**, et l'exclusion est donc caduque — elle est laissée en
place plutôt que réécrite, parce qu'une frontière déplacée se lit mieux que si elle avait
toujours été là.

Six mutations de `prompt_expert_05` ont été mesurées sur la cohorte scellée, selon la procédure
du § 5.2.2 du chapitre 5. La variante retenue, `prompt_expert_32`, ramène le composite de 4,19
à **3,65** et le L1 global de 12,6 à **10,5** ; elle reste **troisième** des seize décideurs,
à 0,05 et 0,04 point des deux meilleurs tabulaires — moins que l'écart entre deux exécutions du
même prompt. Le résultat du lot 2 n'est donc pas renversé : Jev **rejoint** la bande tabulaire,
sous une consigne mieux réglée, il ne la dépasse pas.

Ce que cet addendum ajoute au ticket, et qui vaut pour le chapitre 6 :

- **le non-déterminisme de Jev se chiffre maintenant à l'échelle de la cohorte**, et pas
  seulement par option. Deux exécutions du même prompt aux mêmes graines s'écartent de 0,05
  point de composite et d'au plus 2,9 points de L1 par strate. Le § 6.5 peut citer ce plancher ;
- **la consigne déplace Jev bien plus que le lot 0 ne le laissait croire** : de 13,75
  (`prompt_minimal_02`) à 3,65, soit **10,1 points** de composite entre le prompt le plus nu et
  le mieux réglé du même modèle — à comparer aux 9,56 points déjà rectifiés dans ce ticket ;
- **la variante n'est pas activée** et ne change aucun chiffre publié. `prompt_expert_05` reste
  la consigne du § 6.1.

Trace complète, mécanismes, textes et rejets : `docs/traces/2026-09-21_jev_mutations/README.md`.

---

## 13. Addendum du 2026-09-21 — quatre oublis du même branchement

Le lot 1 a branché `typesafe` sur le nommage (N5) et sur le lancement, mais la règle « ce
décideur lit-il un prompt système ? » était **recopiée à la main dans quatre modules**. Deux ont
été mis à jour, deux non. Les conséquences, toutes constatées le 2026-09-21 :

| | effet |
|---|---|
| `dashboard/experiences.py::_prompt_affiche` | toute exécution Jev affichait « — » dans la colonne `prompt` du registre |
| `experiences/experience.py` | une expérience Jev se rangeait sur une variante **inexistante** sans avertissement ; l'échec ne sortait qu'à la première décision |
| `dashboard/experiences.py::construire_experience` | le formulaire n'écrivait pas `modele` pour ce décideur : le nom, calculé de la version, sortait vide et **l'enregistrement était refusé** — une expérience Jev ne pouvait se déclarer que par son YAML |
| `dashboard/campagne.py::libelle` | le libellé d'une campagne rangeait Jev parmi les témoins, sans sa version |

La liste vit désormais dans `experiences/nommage.py` (`TYPES_LISANT_UN_PROMPT`), et les quatre
consommateurs l'importent. Une seconde constante, `TYPES_A_PROMPT_TRONQUE`, porte le fait que
Jev reçoit la variante **amputée de son bloc `[Output instructions]`** — ce que la fiche de
détail dit, et que la colonne tait pour garder un filtre unique par variante.

**Ce que le test manquait.** `test_le_prompt_affiche_ne_l_est_que_pour_un_decideur_qui_en_lit_un`
n'énumérait que des décideurs **muets** : il gardait le défaut de 2026-09-08 (un prompt affiché
pour un décideur qui n'en lit aucun) et ne pouvait pas voir le défaut symétrique. Il porte
maintenant les deux sens, et trois tests neufs couvrent la validation (`V1`/`V2` de ce ticket),
la mention de troncature dans la fiche, et la création d'une expérience Jev depuis le
formulaire. Les quatre ont été éprouvés par mutation.

Documentation : `docs/arch/dashboard.md`, règle **R23** de
`specs/tableau-experiences-colonnes-et-filtres.md`.
