# Appendices

<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-25 21:07:15 — le .tex correspondant, overleaf/chapters/08_Appendices.tex (compilé par overleaf/supplementary.tex, pas par main.tex), porte cette date en en-tête tant qu'il en est le rendu fidèle. Voir sections/README.md. -->

<!-- Relecture des gallicismes du 2026-09-25, accord de l'auteur (« Corrige ») : tics récurrents (« against » comparatif, « one » pour « un même », « carry », « bound », « under » devant un seuil, « rejoin », « from one X to another », « execute », « brings »), faux-amis (agenda, control, hypothesis, legibility, designate, demanding, chain, globally, bends, recedes), calques de construction et typographie à la française (« 0.9 point », « [a ; b] », « 30.3 % », « 1.06 dollars »). Aucun chiffre ne change ; les prompts et le message de l'annexe D ne sont pas touchés. -->

<!-- Brouillon anglais, article court AAMAS 2027, PLAN.md § 9, annexe D seule. Écrit le
     2026-09-24 à la demande de l'auteur (« on parle de prompt expert ou minimal, ils devraient
     être rajoutés en annexe ; rajoute des liens et des exemples »). Les annexes A–C et E–J
     restent à écrire ; elles viendront dans ce même fichier, dans l'ordre des lettres.
     Destination : matériel supplémentaire, PDF séparé du papier de 8 pages (décision de
     l'auteur du 2026-09-24). Le corps y renvoie en texte brut, « Appendix D ».
     Pas de budget de mots au PLAN pour les annexes.
     ⚠ URL du dépôt anonyme : https://anonymous.4open.science/r/TBD, à remplacer avant la
     soumission. Les chemins de fichier des liens supposent que le dépôt anonymisé reprend
     l'arborescence de ce dépôt-ci. -->

<!-- APPENDIX A — NOTE DE RÉDACTION, à lire avant d'écrire l'annexe (2026-09-25).
     L'annexe A porte le tableau des treize marges que le § 4.1 annonce (« The largest gap is
     0.50 point (Appendix A) »). Le tuteur a annoté ce même tableau dans la version longue
     abandonnée (PDF AAMAS_2027___LLM_v1_KOI, p. 6-7, Table 1 « Demographic control of the
     sealed cohort »). Ses remarques valent pour la nouvelle version :
     1. En-tête « Margin » marqué « ?? » : le mot ne dit pas ce que la ligne contient. Nommer
        la colonne par son contenu, par exemple « Controlled trait », et rappeler dans la
        légende qu'une marge est la part d'un trait dans la population (définition du § 4.1).
     2. En-tête « Verdict » entouré : le mot juge sans dire le critère. Écrire le critère,
        par exemple « Within ±1 pt », et laisser la légende dire que la borne d'équivalence a
        été fixée avant la mesure.
     3. Source « microdata » entourée : on ne sait pas de quoi. Écrire « survey microdata »,
        ou « recomputed from the survey microdata », et dire en une phrase pourquoi certaines
        marges sont recalculées (le rapport publié ne les donne pas).
     4. « Demographic control » surligné dans la légende : dire ce qui est contrôlé contre
        quoi, la cohorte scellée de 1,000 personas contre l'enquête.
     5. Hors tableau, même page : « Each person carries a weight of one » marqué « ? », et le
        paragraphe des marges jugé « not clear ». Si l'annexe mentionne les poids, les
        expliquer (chaque persona compte pour une personne, sans redressement) ou ne pas en
        parler.
     La valeur maximale annoncée au § 4.1 (0.50 point) doit être celle du tableau. -->

*Note on this draft. The main text cites Appendices A, B, D, E and F. Only Appendix D is
written so far. The four others are in preparation and will join this supplementary material
before submission. They give the thirteen cohort margins (A), the 21 input variables (B), the
press experiment (E) and the modal shares by stratum (F).*

<!-- Note ajoutée le 2026-09-25 à la demande de l'auteur (relecture éditoriale, « Rajoute une
     note dans l'appendices ») : les §§ 4.1, 4.2, 5.2 et 6.4 renvoient aux annexes A, B, F et E,
     absentes du fichier. Contenus relevés dans les phrases qui les citent : A, marges de la
     cohorte (§ 4.1) ; B, les 21 variables (§ 4.2) ; E, l'expérience de presse (§ 6.4) ;
     F, parts modales par strate, les 15-19 ans (§ 5.2). Note de brouillon, à retirer quand
     les quatre annexes seront écrites. -->

## Appendix D. The three prompts, and one trip under each

This appendix gives the three prompts of Section 4.4 as the decision-makers received them.
It then follows one trip through three decision-makers, gemini-3.5 under each of the two
prompts and the typed classifier under its own.

### D.1 What each decision-maker receives

A language model receives two messages. The system message is the prompt, followed by the
JSON schema of the expected answer. The user message describes the trip, the persona and the
options. It is built from the trip alone, and the prompt does not change it. Every model runs
at temperature 0 and top-p 1. The thinking level is set to high for gemini-3.5 and
mistral-large, and left unset for gemini-3.1. The simulation then draws the mode at random
from the returned distribution.

<!-- source: canal de rendu, relu dans le code le 2026-09-24.
     Message système = variante de prompts.yaml amputée de son schéma littéral
     (packages/llm_gateway/src/llm_gateway/prompts/engine.py, get_system_prompt →
     _strip_schema_block, regex « \n\s*(?:Expected JSON schema|Schéma JSON attendu)\s*:.* »),
     puis « Expected JSON schema: » et output_schema.json indenté
     (categories/itinary_multi_agent/template.md.j2, bloc marqué SYSTEM). Message
     utilisateur = bloc marqué USER du même gabarit, qui ne lit que les champs de l'agent
     (AgentSpec, packages/mobility_llm/src/mobility_llm/persona.py) : la variante n'y entre pas.
     Paramètres relus le 2026-09-24 dans presente.payload.parameters de la première décision
     de chaque run de modèle de langue de data/experiences/ : temperature 0.0 et top_p 1.0
     partout ; thinking_level « high » pour gemini-3.5-flash-lite et mistral-large-2512,
     None pour gemini-3.1-flash-lite (runs promin02, proexp05, proexp25). max_tokens 4096
     dans les deux runs de D.5. Tirage du mode dans la
     distribution : « mode tiré au sort » dans le champ raison de chaque décision, graine 42
     (graine_tirage). Troncature du consideration set désactivée (cf. 01_introduction.en.md). -->

The typed classifier receives the same prompt, cut before its output instructions. Its typed
output takes their place. The trip reaches it as the same facts, in two parts. One holds the
persona and its context, the other gives one line per option. It returns one probability per
option and writes no text.

<!-- source: services/llm-agents/experiences/decideur_typesafe.py. MARQUEUR_SORTIE =
     « [Output instructions] », instructions_servies() garde texte[:coupe] ; _etat() rend le
     bloc persona sans les options ; _criteres() rend une clé option_<i> par option, valeur
     « Mode <mode>. <description> » ; appel client().system_one(model, state, questions=
     {"mode": Choice(instructions, criteria)}). Test : services/llm-agents/tests/
     test_096_typesafe.py, C2 (l. 242-264) vérifie l'absence de « [Output instructions] ». -->

Table D.1 lists the four files that hold this material in the anonymised repository. The
prompt file stores each prompt under the key given with it below.

*Table D.1. Where each element of this appendix is kept.*

| Element | File |
|---|---|
| The three prompts | [`prompts.yaml`](https://anonymous.4open.science/r/TBD/packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml) |
| The user message | [`template.md.j2`](https://anonymous.4open.science/r/TBD/packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/template.md.j2) |
| The JSON schema | [`output_schema.json`](https://anonymous.4open.science/r/TBD/packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/output_schema.json) |
| The classifier's input | [`decideur_typesafe.py`](https://anonymous.4open.science/r/TBD/services/llm-agents/experiences/decideur_typesafe.py) |

### D.2 The minimal prompt

The minimal prompt gives the task and the output format, and nothing else. It runs to 82 words, excluding the schema, and the prompt file holds it under the key `prompt_minimal_02`.

```text
Select the optimal travel mode taking the persona into account.

[Output instructions]

1. Analyse the profile.
2. Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.
3. Return only a valid JSON object — no markdown, no extra text.
4. Justify the distribution in one concise sentence.
```

<!-- source: prompts.yaml, prompt_minimal_02.content, schéma littéral retiré comme au service
     (voir D.1). 82 mots : _provenance.mots, recompté le 2026-09-24 sur le texte ci-dessus.
     sha256 du texte complet de l'entrée, avis de neutralité du 2026-09-14 :
     8da3812df553043df1496346af656075340c290c03485545d505718f50df751e. -->

### D.3 The expert prompt

The expert prompt adds the four general criteria of Section 4.4, under one heading. Its first
line and its output instructions repeat the minimal prompt, except that the first instruction
reads the profile "through these principles". It runs to 277 words, under the key
`prompt_expert_05`. The language models receive this text.

```text
Select the optimal travel mode taking the persona into account.

Situational trade-off principles:
- Chain friction: Reconstruct the real door-to-door duration (access walk, waiting, in-vehicle trip, egress). If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting.
- Autonomy of older people: For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps to climb, standing while waiting with no bench).
- Carrying logistics: Take into account the physical constraint of loads (shopping, heavy bags, carrier bags). Carrying loads on public transport is off-putting; the trade-off leans towards direct access with no interchange (an immediate neighbourhood walk, or the boot of a private vehicle).
- Working people's life time: For a working person facing a tightly scheduled day, the time taken away from personal life has critical value. Faced with public transport links that significantly increase the duration or impose multiple interchanges, the traveller prefers the efficiency and schedule control of their available vehicle.

[Output instructions]

1. Analyse the profile through these principles.
2. Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.
3. Return only a valid JSON object — no markdown, no extra text.
4. Justify the distribution in one concise sentence.
```

<!-- source: prompts.yaml, prompt_expert_05.content, schéma retiré. 277 mots
     (_provenance.mots, recompté le 2026-09-24). sha256 de l'avis de neutralité du
     2026-09-14 : 5f55688f9cb3ba3e1e6c6f96549a339858ac72b110d9bdc7d14651c216b53ef4.
     Seule différence avec prompt_minimal_02 hors bloc de principes, vérifiée ligne à ligne :
     consigne 1, « Analyse the profile. » → « Analyse the profile through these
     principles. ». Servi à gemini-3.1, gemini-3.5 et mistral-large (tableau 1). -->

### D.4 The classifier's expert prompt

The classifier's prompt differs from the expert prompt in its first criterion only. Its chain
friction bullet adds the other side of the trade-off, a direct walk that is itself the long
part of the journey. The other lines are those of D.3. It runs to 318 words, under the key
`prompt_expert_32`.

```text
- Chain friction: Reconstruct the real door-to-door duration on both sides — access walk, waiting, in-vehicle trip and egress on one; the unbroken walking effort on the other. If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting. If the direct walk is itself the long part of the journey, that simplicity is paid in time and fatigue, and it stops being the easy option.
```

<!-- source: prompts.yaml, prompt_expert_32 : _provenance.role « la puce « Chain friction »
     réécrite à deux versants », obtention « identique à 'prompt_expert_05' hormis la
     modification décrite dans `role`. Aucune autre ligne ne bouge », mots 318 ; comparaison
     ligne à ligne refaite le 2026-09-24, une seule ligne diffère. Réglée pour jev-1.13.0 sur
     la cohorte scellée (c1), variante retenue A2 : docs/traces/2026-09-21_jev_mutations/README.md.
     ⚠ Depuis la décision de l'auteur du 2026-09-24, le prompt du classifieur se règle sur la
     cohorte de calibration (c2). Ce texte est à remplacer par celui du re-réglage, s'il
     diffère ; la colonne du classifieur du tableau D.2 aussi.
     ⚠ Ce prompt ne porte AUCUNE puce météo. La puce « Real exposure to the weather » est
     celle de prompt_expert_25, réglée pour gemini-3.1 et absente de l'article. Le § 4.4
     disait le contraire jusqu'au 2026-09-24 ; corrigé dans 04_bench.en.md. -->

### D.5 One trip under the three decision-makers

We chose this trip by hand, for clarity, and it is not representative of the cohort.
Raymond, 45, leaves for a shop at 13:37 on the scored day of the sealed cohort. The three
decision-makers received the same six options. The message below is the user message that
both language models received.

```text
--- agent_id=393781 | Destination: shop | Departure: 13:37 ---
**Context:** Weather: 28°C, Partly cloudy. Today 18°C to 33°C, sunrise 06:19, sunset 21:39. Rain expected in the morning (0.8 mm over the day).
**Weather later:** evening 13°C, Clear/Sunny.
Raymond, 45, Full-Time Worker (household of 4, very low income). Usual trip purposes: Shopping. Lives in: 1st ring

**Further trips planned today:**
    · 14:47 → shop (≈1.4 km)

**Trip options** (6 options, indices 0 to 5):
- [0] foot: Estimated duration: 16 minutes. Distance: 1.3 km.
- [1] foot: Travel time: 17 minutes, including 17 minutes of walking.
    · Walk to 'shop': 17 minutes.
- [2] car: Travel time: 4 minutes, including 1 minute of access and parking. Distance: 1.5 km.
    · Walk to the car: 1 minute.
    · Driving: 3 minutes.
- [3] foot,bus,foot: Travel time: 43 minutes, including 42 minutes of walking. Has no public transport pass.
    · Walk to 'Collège Picasso': 21 minutes.
    · Bus 'L11' to 'Frouzins Complexe Sportif': 1 minute.
    · Walk to 'shop': 21 minutes.
- [4] foot,bus,foot: Travel time: 34 minutes, including 33 minutes of walking. Has no public transport pass.
    · Walk to 'Frouzins Tréville': 10 minutes.
    · Bus '321' to 'Rouget de Lisle': 1 minute.
    · Walk to 'shop': 22 minutes.
- [5] foot,bus,foot: Travel time: 35 minutes, including 34 minutes of walking. Has no public transport pass.
    · Walk to 'Rouget de Lisle': 14 minutes.
    · Bus '321' to 'Frouzins Tréville': 1 minute.
    · Walk to 'shop': 19 minutes.



Reply with the final JSON object containing the recommendations for 1 persona(s).
For each persona, copy its `agent_id` **exactly** as provided above (numeric identifier only, without the word "PERSONA" and without the persona's name).
For each persona, rate **all** of its options — one `probabilities` entry per option, with its `index` and its `mode` copied as they appear — and make the `probability` values sum to 100. An option this persona would never take receives 0.
Only the `- [n]` lines are options: the « · » sub-bullets detail the steps of an option and never receive a `probabilities` entry. Indices restart from 0 in each persona block — use only those shown in brackets in the block of the persona you are rating, never a numbering continued from one persona to the next.
```

<!-- source: décision person_id 393781, activity_id 6b8e522b-71c5-53f7-8fd8-162259861328,
     cohorte v6 (première cohorte), jeu population_1000_AAMAS_v6_20260316_EN_c, graine 42.
     Trois runs, décisions relues le 2026-09-24 dans leur decisions.jsonl :
     - prompt minimal, gemini-3.5 : data/experiences/exp_gemini-35-fl_promin02_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim/executions/2026-09-16_19_05_45 ;
     - prompt expert, gemini-3.5 : data/experiences/exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim/executions/2026-09-16_22_20_25 ;
     - classifieur typé, sa consigne : data/experiences/exp_jev-1130_proexp32_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_nosim/executions/2026-09-21_10_14_52.
     Message utilisateur RE-RENDU depuis presente.payload.agents[0] par PromptManager.render,
     une persona par requête comme en production ; gabarit et moteur inchangés depuis le
     commit 180497b (2026-09-14), antérieur aux deux runs. Texte identique à l'octet sous
     prompt_minimal_02 et prompt_expert_05 (assertion), sha256[:12] = f8931ca4f59f. Payloads
     des deux runs gemini identiques champ à champ ; jeu d'options (mode, durée) identique
     dans les trois runs. Les trois lignes vides avant « Reply with » sont celles du gabarit.
     Le classifieur a reçu ces mêmes champs sous sa forme propre (D.1) ; ce texte-là n'est pas
     reproduit ici.
     Choix du trajet : prénom toulousain demandé par l'auteur le 2026-09-24 ; parmi les
     trajets à six options où les deux prompts donnent un mode majoritaire différent et où
     les trois décideurs ont reçu le même jeu d'options. Aucun tirage : « chosen by hand ».
     ⚠ Un premier candidat, persona 1178884, a été écarté : le classifieur n'y avait pas reçu
     la voiture, sa propre chaîne de véhicules ayant tiré autrement plus tôt dans la journée. -->

Table D.2 gives the three answers, in percent. The last row is the mode drawn from each
distribution, under the same seed in all three runs.

*Table D.2. Probability given to each option of Raymond's trip, in percent.*

| Option | Minimal prompt, gemini-3.5 | Expert prompt, gemini-3.5 | Typed classifier, its expert prompt |
|---|---:|---:|---:|
| [0] foot, 16 min | 30 | 45 | 52 |
| [1] foot, 17 min | 10 | 45 | 20 |
| [2] car, 4 min | 50 | 10 | 27 |
| [3] foot, bus, foot, 43 min | 0 | 0 | 0 |
| [4] foot, bus, foot, 34 min | 5 | 0 | 1 |
| [5] foot, bus, foot, 35 min | 5 | 0 | 0 |
| Mode drawn | car | foot | car |

<!-- source: poids_presentes des trois décisions citées ci-dessus, en fractions :
     minimal [0.3, 0.1, 0.5, 0.0, 0.05, 0.05] ; expert [0.45, 0.45, 0.1, 0.0, 0.0, 0.0] ;
     classifieur [0.52, 0.2, 0.27, 0.0, 0.01, 0.0], reponse_brute {"option_0": 0.52,
     "option_1": 0.2, "option_2": 0.27, "option_3": 0.0, "option_4": 0.01, "option_5": 0.0},
     « choice »: option_0, confidence 0.42. Mode tiré : champ retenue, index_presente 2, 1, 2.
     Réponses brutes gemini : probabilités 30/10/50/0/5/5 et 45/45/10/0/0/0, sommes 100. -->

The language models justified their distributions in one sentence each. Under the minimal
prompt, gemini-3.5 wrote the following sentence.

> Raymond prefers the speed and shelter of a car for his short shopping trip during inclement weather.

Under the expert prompt, the same model wrote the following one.

> With a very short distance to the shop and low income constraints, walking directly is the preferred choice.

The first justification thus invokes bad weather that the message does not describe (28 °C,
partly cloudy, rain in the morning only). The second justification names none of the four
criteria.

<!-- source: champ reponse_brute[0].reason des deux décisions gemini, cité à la lettre. Météo :
     champ context du payload, reproduit dans le message ci-dessus. -->

Under both prompts, gemini-3.5 gives the three bus options at most 10% combined. The expert
prompt takes forty points from the car and ten from the bus, and gives all fifty to walking.
The classifier gives walking 72%, between the two.

<!-- source: Table D.2. Bus : 0 + 5 + 5 = 10 sous le minimal, 0 sous l'expert. Voiture 50 → 10,
     bus 10 → 0, marche 30 + 10 = 40 → 45 + 45 = 90, soit + 50 = 40 + 10. Classifieur, marche 52 + 20 = 72, entre 40 et 90 ;
     voiture 27, entre 50 et 10.
     Phrase retirée le 2026-09-24 : « Its prompt was tuned on the first cohort, so its column
     is in sample. » Le § 4.4 dit maintenant le prompt du classifieur réglé sur la cohorte de
     calibration (décision de l'auteur). ⚠ La colonne ci-dessus reste celle de
     prompt_expert_32, réglé sur c1 : à rejouer sous le prompt re-réglé sur c2, et la phrase
     « 72 %, between the two » à revérifier sur la nouvelle colonne. -->

<!--
=== SECTION REPORT ===
Section        : 08 — Appendices (Appendix D only)
File           : docs/paper/article-court/sections/08_appendices.en.md
Words / budget : see the checker output ; the plan sets no budget for the appendices.
Skeleton       :
  This appendix gives the three prompts of Section 4.4 as the decision-makers received them.
  A language model receives two messages.
  The typed classifier receives the same prompt, cut before its output instructions.
  The minimal prompt gives the task and the output format, and nothing else.
  The expert prompt adds the four general criteria of Section 4.4, under one heading.
  The classifier's prompt differs from the expert prompt in its first criterion only.
  We chose this trip by hand, for legibility, and it is not representative of the cohort.
  Table D.1 lists the four files that hold this material in the anonymised repository.
  Table D.2 gives the three answers, in percent.
  The language models justified their distributions in one sentence each.
  Under both prompts, gemini-3.5 gives the three bus options ten percent at most, together.
Terms defined here : none new ; system message and user message are used without a gloss,
  the target reader knowing language models.
Terms used, undefined upstream : none. Minimal prompt, expert prompt, general criteria and
  typed classifier come from 4.4.
Figures cited  : 82, 277, 318 words — prompts.yaml _provenance.mots, recounted.
  Table D.2 and the 72 % — the three decisions named in the source comment. The
  classifier's column is in sample, said in the text.
Placeholders   : the repository URL, https://anonymous.4open.science/r/TBD, at four links.
  Asked for by the author ; it breaks R14 until the real URL replaces it.
Left out       : the classifier's own input text for the trip (described in D.1, not
  reproduced) ; the JSON schema (linked, not reproduced).
Flags for the author :
  1. Rule 11 bars repository names from the body. The appendix names the three prompt keys
     and links four files, because a reader who wants to replay needs them. The body still
     names none.
  2. The four links assume the anonymised repository keeps this repository's layout.
  3. The body of 4.4 said the classifier's prompt adds a fifth criterion, real exposure to
     the weather. The prompt text printed in D.4 has no such bullet. 4.4 is corrected in the
     same pass.
=== END SECTION REPORT ===
-->
