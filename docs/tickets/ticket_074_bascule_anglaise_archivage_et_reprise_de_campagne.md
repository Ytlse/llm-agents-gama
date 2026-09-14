# Ticket 074 — Bascule du dispositif en anglais, archivage froid et reprise automatisée de la campagne

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-14.
>
> **Catégorie** : Expériences & Cognition (🧠) / Plateforme (🛠️)
> **Statut initial** : `à faire`
>
> **Remplace** le volet « ablation bilingue » du [ticket 072](ticket_072_impact_langue_et_cadrage_culturel_llm.md) :
> on ne mesure pas l'écart français/anglais, on bascule et on refait la campagne une fois.
>
> **Touche** : `prompts.yaml`, la couche de rendu, le jeu scellé, la plateforme d'expériences,
> le tableau de bord, et le chapitre 4 de l'article (§ 4.3).

---

## 0. Point de départ — à lire d'abord

**État au 2026-09-14 : rien n'est implémenté.** Le ticket est cadré, les cinq arbitrages sont
rendus (§ 9), l'inventaire des traductions est extrait du code. Aucun fichier de production n'a
été touché.

**Le lot A est bloquant.** Ne rien traduire, ne rien régénérer, ne rien renommer avant que l'état
français ne soit gelé dans l'archive froide et que le test de non-accessibilité ne passe.
Le contenu exact de l'archive se présente à l'auteur **avant** tout déplacement.

**Ce qui est déjà établi, à ne pas re-chercher :**

| Fait | Où c'est écrit |
|---|---|
| Le prompt actuel est **mixte** FR/EN, par sédimentation et non par choix | § 1.1, avec un extrait réel |
| Le substrat n'est **pas** français : `purpose`, traits et durées sont anglais ou numériques | § 1.2 |
| Les 22 variantes, 3 gabarits, 9 descriptions de schéma, 7 gabarits d'itinéraire, 47 libellés météo | [`specs/ticket_074/inventaire_traduction.md`](../../specs/ticket_074/inventaire_traduction.md) |
| Les 10 expériences LLM à rejouer, nommément ; les 14 témoins exclus et pourquoi | § 5.1 |
| La moitié de la pipeline existe déjà (`ATTENDRE_FENETRE`, `quota.py`, file, ordonnanceur) | § 5, tableau « Existant à réutiliser » |

**Les trois pièges qui coûtent cher s'ils sont manqués :**

1. **Ne pas traduire les étiquettes de mode** — `parse_option_modes` les relit dans le texte du
   prompt (`models.py:192`). Les traduire casse la loss de calibration et `moves.csv`.
2. **Ne pas traduire les libellés d'occupation à la source** — clés de jointure
   (`scripts/synthesis/frames.py:138`).
3. **Ne pas écraser `Condition` dans `data/weather/Codes meteo.csv`** — ajouter `Condition_EN` ;
   les historiques météo s'y réfèrent par `CodeMétéo`.

**L'article est verrouillé.** Le § 4.3 et la limite du chapitre 8 figurent aux critères
d'acceptation, mais toute écriture dans `docs/paper/article/` passe par la skill `article-verrou`
et un accord humain explicite.

---

## 1. Pourquoi l'anglais — et pourquoi maintenant

### 1.1 L'état actuel n'est pas « un prompt en français »

Extrait d'un prompt réellement envoyé (`experiments/current/llm_exchanges.jsonl`) :

```
--- agent_id=2348 | Destination : work | Départ : 06:48 ---
Thibault, 58 ans, Travail à plein temps (seul(e), revenu très faible)
- [0] bicycle: Durée estimée : 2 hours, 9 minutes. Distance : 37.5 km.
    · Marche jusqu'à 'work' : 7 minutes.
```

Étiquettes et prose en français ; motifs (`work`, `home`, `other`), étiquettes de mode
(`bicycle`, `foot,bus,foot`) et durées (`2 hours, 9 minutes`) en anglais. **Ce mélange n'a jamais
été décidé** : il résulte de la sédimentation de `humanize.precisedelta` (locale anglaise par
défaut), des énumérés d'eqasim et de gabarits écrits à des moments différents.

Le défaut est de **forme, pas de validité** : la couche de rendu est commune à toutes les variantes
de `prompts.yaml`, à tous les bras et à tous les modèles. Elle ne fait varier aucune comparaison.
Mais elle est publiée en annexe (ticket 069), et elle s'y lit comme un travail inachevé.

### 1.2 L'argument que l'on croyait avoir, et qui ne tient pas

Le français a longtemps été justifié par la « fidélité du substrat » : nomenclatures françaises,
ancrage territorial. **Vérification faite, c'est faux.** Un enregistrement du jeu scellé
(`data/jeux/population_1000_AAMAS_v5_20260316/propositions.jsonl`) contient `"purpose": "work"`,
des coordonnées, des timestamps et des distances. Les traits sont en anglais — `llm_agent.py:227`
contient un `_income_map` qui traduit `"Very Low"` en `"très faible"`. **Le substrat est en anglais
et en chiffres ; c'est nous qui le traduisons en français.** Les seuls éléments réellement français
sont des noms propres (`'Empalot Métro'`, `'Ramonville'`), invariants par langue.

### 1.3 Ce que dit la littérature

Le corpus reconstitué de [`docs/paper/mémoire/`](../paper/mémoire/) tranche dans ce sens, avec des
réserves qu'il faut énoncer honnêtement.

**En faveur de l'anglais :**

- **Qi et al., Findings EMNLP 2025** ([arXiv:2505.22888](https://arxiv.org/abs/2505.22888)) —
  imposer une trace de raisonnement hors anglais améliore la lisibilité mais **dégrade
  l'exactitude**. Nos prompts imposent précisément une procédure de raisonnement en 3 ou 4 étapes.
- **Liu et al., Findings ACL 2025** ([arXiv:2502.17945](https://arxiv.org/abs/2502.17945)) — dans
  les recommandations agentiques, le biais de langue locale est prévalent et **le chain-of-thought
  l'aggrave** en langue non anglaise. C'est exactement notre régime.
- **Bazoge et al., 2026** ([arXiv:2605.19173](https://arxiv.org/abs/2605.19173)) — comparaison
  anglais/français sur 180 vignettes de raisonnement décisionnel, 5 modèles, 2 évaluateurs experts :
  4 modèles sur 5 sont meilleurs en anglais (écart 0,37 à 0,91 point sur 18, p ajusté < 0,05).
- **Bulté & Rigouts Terryn, *Computational Linguistics* 2026**
  ([arXiv:2511.03980](https://arxiv.org/abs/2511.03980)) — *« prompt language is an ineffective cue
  for cultural alignment »*. Le cadrage culturel explicite pèse davantage que la langue,
  **et il est aussi efficace formulé en anglais**. L'ancrage toulousain ne se perd donc pas.

**Réserves à ne pas taire :**

- **Ying et al., ACL 2025** ([arXiv:2505.24635](https://arxiv.org/abs/2505.24635)) — « synergie
  langue-culture » : un modèle répond mieux à une question de culture locale posée dans la langue
  correspondante. Nous perdons ce bénéfice potentiel.
- **Soegeng et al., 2026** ([arXiv:2605.22137](https://arxiv.org/abs/2605.22137)) — prompter en
  anglais *« induit un biais occidental-centré »*. **Aucune contre-mesure dans ce ticket** : le
  renforcement du cadrage territorial a été écarté (arbitrage Q3 du 2026-09-14). L'ancrage reste
  donc ce qu'il est aujourd'hui — la mention « personnes vivant à Toulouse ». À déclarer comme
  limite au chapitre 8, sans l'habiller.
- **Ananthram et al., ICLR 2025** ([arXiv:2406.11665](https://arxiv.org/abs/2406.11665)) — le
  français étant bien représenté au pré-entraînement, le coût du français restait faible. Ce
  ticket n'est donc **pas une correction d'erreur**, c'est une mise au propre.

### 1.4 Pourquoi maintenant plutôt que jamais

Toute modification du texte d'un prompt change les décisions : franciser une durée coûte le même
prix qu'angliciser tout le dispositif — **une reprise complète de la campagne**. À prix égal,
franciser est dominé : c'est le choix que la littérature soutient le moins, et il reste inatteignable
(cf. § 3.2, les étiquettes de mode doivent rester anglaises). Si l'on paie une reprise, c'est pour
l'anglais.

---

## 2. Lot A — Archive froide

**Objectif :** figer l'état « français » avant toute modification, de façon **inaccessible à chaud**
— ni lue par le code, ni listée par le registre, ni résolue par le `PromptManager`.

À distinguer du statut `archivee` existant (`make experience-statuer … STATUT=archivee`), qui ne
change que la **visibilité** : les fichiers restent en place et restent lisibles. Ici on déplace.

- **A-1** — Créer `archive/2026-XX-XX_avant_bascule_anglaise/` à la racine, hors dépôt git
  (`.gitignore`), conformément à la doctrine « traces sur disque, pas dans git ».
- **A-2** — Y déplacer : `prompts.yaml` (les 18 variantes, empreintes `_neutralite` comprises),
  les définitions et exécutions d'expériences de `data/experiences/`, les jeux scellés
  `data/jeux/population_1000_AAMAS_v5*`, les dossiers d'`experiments/` référencés par l'article.
- **A-3** — Écrire un `MANIFEST.yaml` : date de gel, `sha256` de chaque fichier, commit git au
  moment du gel, et la liste des chiffres de l'article qui en dérivent.
- **A-4** — **Garantir la non-accessibilité à chaud.** `PromptManager`, `experiences/registre.py`
  et le lanceur doivent ignorer ce chemin. Un test le vérifie : aucune fonction de chargement ne
  résout un nom depuis `archive/`.
- **A-5** — Aucune suppression définitive (contrainte de `specs/hygiene-prompts-et-plateforme-experiences.md`).

---

## 3. Lot B — Traduction

### 3.0 Portée — arrêtée le 2026-09-14

**Tout est traduit**, pas seulement les variantes encore utilisées. Les 22 variantes de
`prompts.yaml` y passent, y compris les 18 qui ne sont référencées que par des exécutions
archivées : laisser la moitié du fichier en français reconduirait exactement le défaut de tenue
que ce ticket vient corriger.

L'inventaire exhaustif, extrait du code et non reconstitué, vit dans
[`specs/ticket_074/inventaire_traduction.md`](../../specs/ticket_074/inventaire_traduction.md) —
22 variantes, 3 gabarits, 9 descriptions de schéma, 7 gabarits d'itinéraire, 5 littéraux de
persona, ~12 littéraux météo et **47 libellés de conditions météo en CSV**.

### 3.1 Les sept surfaces à traduire

| # | Surface | Fichier | Contenu français |
|---|---|---|---|
| B-1 | Prompts système | `packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml` | 18 variantes |
| B-2 | Gabarits utilisateur | `packages/mobility_llm/.../categories/*/template.md.j2` (4) | Étiquettes, consignes de sortie |
| B-3 | Schémas de sortie | `packages/mobility_llm/.../categories/*/output_schema.json` (4) | Champs `description` |
| B-4 | Descriptions d'itinéraire | `services/llm-agents/text_helper/templates/tpl/descriptions/*.j2` (7) | « Durée estimée », « dont … de marche », « Marche jusqu'à », « [correspondance] », « Car scolaire liO (gratuit) » |
| B-5 | Récit de persona | `services/llm-agents/urban_mobility_agents/agents/llm_agent.py:221` | `_income_map`, « ans », « seul(e) », « famille de N pers. » |
| B-6 | Bulletin météo | `weather_loader.py:367` **+ `data/weather/Codes meteo.csv`** | Rendu météo (~12 littéraux) **et 47 libellés de conditions** |
| B-7 | Libellés d'occupation | remontent à `scripts/synthesis/frames.py:138`, `scripts/progedo_logit/` | « Travail à plein temps » |

⚠️ **B-7 : traduire à l'affichage uniquement.** Ces libellés servent de **clés de jointure** dans
`frames.py` et les scripts PROGEDO. Les traduire à la source casse les jointures.

⚠️ **B-6 est le seul cas qui touche un fichier de données.** Les 47 conditions de
`data/weather/Codes meteo.csv` (« Légères averses de pluie à proximité », « Ciel dégagé/Ensoleillé »…)
ne sont pas dans du code. Ajouter une colonne `Condition_EN` plutôt que d'écraser `Condition` :
les historiques météo de `data/weather/*.csv` s'y réfèrent par `CodeMétéo`, et l'écrasement
rendrait les archives illisibles.

### 3.2 Ce qu'il est interdit de traduire

**Les étiquettes de mode** (`car`, `bicycle`, `foot,bus,foot`). `models.py:192` le documente :
`parse_option_modes` **relit ces étiquettes dans le texte du prompt**, et elles alimentent
`categorize_mode`, la loss de calibration et les parts modales de `moves.csv`. Elles sont déjà
anglaises — la bascule les laisse intactes, ce qui est un avantage de cette direction.

**Les noms propres** : arrêts GTFS, lignes, communes. Ils restent en français, comportement normal
dans n'importe quelle langue.

### 3.3 Cadrage territorial — écarté

Une version antérieure de ce ticket proposait d'étoffer le cadrage (Tisséo, armature urbaine,
ordres de grandeur locaux) pendant la réécriture. **Écarté le 2026-09-14.** La traduction ne change
donc qu'une seule variable, ce qui rend l'écart attribuable. Conséquence assumée : on abandonne le
levier faible (la langue) sans activer le levier fort (le cadrage). À dire tel quel au chapitre 8.

### 3.4 Contrôles

- **B-8** — Chaque variante repasse par l'agent `prompt-auditor` ; les blocs `_neutralite`
  (`sha256_texte`, `le`, `verdict`) sont recalculés. Une variante non auditée est refusée au
  chargement (mécanisme déjà livré, § 4.1 de la spec hygiène).
- **B-9** — Un test de non-régression linguistique : aucun caractère accentué ni mot français dans
  le prompt rendu, **hors noms propres** (liste blanche depuis le GTFS et le référentiel communes).

---

## 4. Lot C — Régénération de la population et renommage des prompts

### 4.1 Population

- **C-1** — Régénérer la cohorte scellée en **v6**, selon la procédure du ticket 052, à partir de
  `scripts/data/population/generate_population.ipynb` et `cerema_values.yaml`.
- **C-2** — `MANIFEST.yaml` : `sha256`, `person_count`, `trip_count` **dérivés, jamais saisis à la
  main** ; la v5 reste dans l'archive froide.
- **C-3** — Mettre à jour `defaults.inputs` de `docs/paper/methode/experience_plan/experiments.yaml`.

> **Arbitrage du 2026-09-14 : on régénère, et la v5 part à l'archive froide (lot A).**
> À noter : la régénération n'est pas *techniquement* requise. L'audit de la v5 montre que le seul
> trait français atteignant le prompt est `main_occupation`, et que son équivalent anglais
> (`professional_activity`) est déjà présent dans chaque enregistrement — inverser la préférence
> ligne 225 de `llm_agent.py` suffirait. Les traits `personal_bike`, `residence_zone` et
> `housing_type` sont français mais dormants depuis le 2026-08-26. La régénération est donc une
> remise à neuf voulue, pas une dépendance.
>
> - **C-1b** — Les enrichisseurs (`enrich_personal_bike.py`, `enrich_residence_zone.py`,
>   `enrich_housing_type.py`, `fix_minor_traits.py`) produisent aujourd'hui des valeurs françaises.
>   La v6 doit sortir **en anglais de bout en bout** : ces scripts sont à corriger, sinon la
>   régénération reproduit le problème.

### 4.2 Renommage générique des prompts

Les 18 noms actuels mélangent quatre conventions : `prompt_optimise_v5`, `expert_chaine_m7`,
`b_min`, `b0_pristine`, `persona_v3`, `expert`. Un lecteur extérieur ne peut pas en déduire la
famille ni la place dans la série.

- **C-4** — Schéma proposé : `<famille>_<trait>_<nn>` — `minimal_01`, `expert_chain_01`,
  `expert_persona_01`, `expert_baseline_01`. La famille (`minimale` / `experte`) reste portée par
  le champ `familles` existant ; le nom cesse de la contredire.
- **C-5** — Conserver un champ `_ancien_nom` par variante : les définitions d'expériences archivées
  et les traces référencent les noms actuels, et le registre doit continuer à les résoudre en
  lecture.
- **C-6** — Script de migration `scripts/migrations/renommer_prompts.py`, sur le modèle de
  `renommer_experiences.py` : **à blanc par défaut**, `APPLIQUER=1` pour écrire.

---

## 5. Lot D — Pipeline de reprise de campagne

Une grande partie existe déjà. Ce lot **assemble**, il ne réinvente pas.

**Existant à réutiliser :**

| Brique | Où |
|---|---|
| Reprise sur renouvellement de quota | `make experience-lancer ATTENDRE_FENETRE=1` (dort jusqu'au reset, repart seul) |
| Calcul de l'heure de reset | `packages/llm_gateway/src/llm_gateway/core/quota.py` — `next_quota_reset()`, `seconds_until_quota_reset()` (fuseau par fournisseur, minuit Pacifique pour Gemini) |
| File d'attente par clé | `make experience-file` / `experience-actives` / `experience-defiler` |
| Ordonnanceur | `make experience-ordonnancer` |
| Estimation de coût | `make experience-estimer EXP=<nom>` |

### 5.1 Périmètre de la campagne — arrêté le 2026-09-14

Le registre compte **24 expériences actives**. Leur champ `decideur` les sépare nettement :

| | Nombre | Dépend du prompt ? | Dans la campagne ? |
|---|---|---|---|
| Décideurs LLM (`gemini-3.8-flash` ×2, `gemini-3.1-flash-lite` ×3, `gemini-3.5-flash-lite` ×5) | **10** | oui | ✅ **à rejouer** |
| Témoins déterministes (`aleatoire`, `duree_minimale`, `majoritaire_voiture`, et les modèles `rf`, `lgbm`, `mnl`, `klr`) | **14** | non — aucun appel LLM | ❌ inchangés |

**Les 14 témoins ne sont pas rejoués** : ils ne lisent aucun prompt, leurs sorties sont
indépendantes de la langue. Ils restent comparables aux nouvelles exécutions LLM, à condition que
la population soit la même — d'où une contrainte : **ils doivent être rejoués sur la v6** si la
régénération change les chaînes d'activités. À vérifier au gel (cf. D-7).

Les 10 expériences LLM à rejouer :

```
exp_agy-gemini-38-f_promin_jtir_pop-1000_AAMAS_v5_t0_nosim
exp_agy-gemini-38-f_promin_jtir_pop-1000_AAMAS_v5_escort66_t0_nosim
exp_gemini-31-fl_promin_jtir_pop-1000_AAMAS_v5_escort66_t0_nosim
exp_gemini-31-fl_promin_jtir_pop-population_1000__t0_nosim
exp_gemini-31-fl_expgem38v2_jtir_pop-1000_AAMAS_v5_t0_nosim
exp_gemini-35-fl_promin_jtir_pop-population_1000__t0_nosim
exp_gemini-35-fl_expgem38v2_jtir_pop-1000_AAMAS_v5_t0_nosim
exp_gemini-35-fl_expgem38v2_jtir_pop-1000_AAMAS_v5_t0_nosim_2
exp_gemini-35-fl_expgem38v3_jtir_pop-1000_AAMAS_v5_t0_nosim
exp_gemini-35-fl_prooptv4_jtir_pop-1000_AAMAS_v5_t0_nosim
```

Leurs noms portent la population (`pop-1000_AAMAS_v5`) : ils seront **renommés** par la bascule
en v6, via `make experiences-renommer` (spec `nommage-canonique-experiences`).

**À construire :**

- **D-1** — Notion de **campagne** : un lot nommé d'expériences à rejouer, défini par un fichier
  `campagnes/<nom>.yaml` listant les expériences, leur ordre et leurs dépendances.
- **D-2** — `make campagne-lancer NOM=<nom>` : enfile toutes les expériences de la campagne,
  délègue à l'ordonnanceur existant, et pose `ATTENDRE_FENETRE=1` par défaut.
- **D-3** — **Reprise automatique au renouvellement**, au niveau de la campagne et non plus de
  l'expérience seule : à l'épuisement des quotas de **tous** les fournisseurs éligibles, la campagne
  se met en sommeil jusqu'au `next_quota_reset()` le plus proche, puis reprend **là où elle s'est
  arrêtée** — pas au début.
- **D-4** — État de campagne persistant (`campagnes/<nom>/etat.json`) : expérience courante, faites,
  restantes, échouées, horodatages, nombre de mises en sommeil. Survit à un redémarrage.
- **D-5** — Journalisation conforme à la doctrine du dépôt : début et fin de chaque expérience avec
  sa durée, compteurs (faites / restantes / ignorées), **succès explicite**, et `[ALARME]` en ERROR
  sur front montant si une expérience échoue deux fois de suite ou si le sommeil dépasse 26 h.
- **D-6** — `make campagne-etat NOM=<nom>` et `make campagne-arreter NOM=<nom>`.
- **D-7** — **Garde de comparabilité** : au gel de la v6, comparer ses chaînes d'activités à celles
  de la v5. Si `trip_count` ou les chaînes changent, les 14 témoins déterministes doivent être
  rejoués eux aussi — ils sont bon marché (aucun appel LLM), mais les oublier casserait
  silencieusement la comparaison LLM / témoin. Le refus d'apparier des exécutions non comparables
  existe déjà (`registre.py:636`, règle P6) : s'y appuyer plutôt que de le réimplémenter.
- **D-8** — Budget : la campagne porte **10 expériences**, pas 24. `make experience-estimer`
  donne le coût par expérience avant lancement ; la campagne en publie la somme.

---

## 6. Lot E — Onglet de pilotage

- **E-1** — Nouvel onglet dans `scripts/dashboard/app.py` : ajouter `("campagne", "🔁 Campagne")`
  à la liste `ONGLETS` (ligne 1693) et le déballer dans le `st.tabs(...)` correspondant. Le slug
  vit dans l'URL (`?onglet=campagne`) — mécanisme déjà en place.
- **E-2** — Rendu paresseux obligatoire : `if _should_render("campagne")`, comme les autres.
- **E-3** — Module dédié `scripts/dashboard/campagne.py` (ne pas alourdir `app.py`), sur le modèle
  de `experiences.py`.
- **E-4** — Contenu : avancement global (faites / total, barre), expérience en cours et sa durée,
  file d'attente, **temps restant avant le prochain renouvellement de quota** (via
  `seconds_until_quota_reset()`), historique des mises en sommeil, expériences en échec avec leur
  motif, et boutons lancer / arrêter passant par le registre de jobs existant.
- **E-5** — Garde d'exception autour du rendu : une faute de frappe ne doit pas faire disparaître
  l'onglet voisin (précédent documenté ligne 458 de `app.py`).
- **E-6** — Tests dans `scripts/tests/`, sur le modèle de `test_dashboard_app.py`, avec
  `DASHBOARD_EAGER=1`.

---

## 7. Ordre d'exécution

```
A (archive froide)  ──►  B (traduction)  ──►  C (population v6 + renommage)
                                                      │
                          D (pipeline campagne)  ◄─────┘
                                    │
                          E (onglet de pilotage)
                                    │
                          Reprise de la campagne
```

**A est bloquant** : rien ne bouge avant que l'état français ne soit gelé et vérifié.
D et E peuvent être développés en parallèle de B et C — ils n'en dépendent pas.

---

## 8. Critères d'acceptation

- [x] L'archive froide existe, porte son `MANIFEST.yaml` avec les `sha256`, et **un test prouve
      qu'aucun chargeur du code ne résout un nom depuis `archive/`**.
- [x] Un prompt rendu ne contient plus de français hors noms propres (test B-9 vert).
- [x] Les **22** variantes portent un bloc `_neutralite` daté d'après la traduction, empreinte
      recalculée. *Verdicts inchangés par la traduction : 8 conformes, 11 conformes avec
      réserve, 3 non conformes — une traduction ne répare pas un prompt non conforme, et
      prétendre le contraire aurait été le seul moyen de tenir le « verdict `conforme` »
      écrit ici.*
- [x] Les étiquettes de mode sont inchangées et `parse_option_modes` passe ses tests.
- [x] La cohorte v6 est scellée (`sha256 412efada…`, 13 marges conformes, 0 à corriger), son
      `trip_count` est dérivé (894 mobiles, 3 299 déplacements), et `experiments.yaml` la référence.
- [x] **Aucun trait de la v6 n'est en français** (`main_occupation`, `personal_bike`,
      `residence_zone`, `housing_type` compris) — les enrichisseurs sont corrigés, pas contournés.
      Vérifié sur les 22 champs des 1 000 personas du fichier scellé : aucune valeur française.
- [x] `data/weather/Codes meteo.csv` porte une colonne `Condition_EN` pour ses 47 conditions,
      `Condition` étant laissée intacte pour les historiques.
- [x] Les prompts portent des noms génériques ; `_ancien_nom` permet de relire les traces archivées.
- [x] `make campagne-lancer` rejoue **les 22 expériences** (14 témoins puis 8 LLM — voir le
      lot D ci-dessous pour le passage de 10 à 22), se met en sommeil à l'épuisement des
      quotas et **reprend d'elle-même au renouvellement, là où elle s'était arrêtée**.
- [x] La garde D-7 a statué : **comparables en l'état**. Les 14 témoins ne lisent aucun prompt,
      et la v6 porte les mêmes 1 000 `person_id` et 0 chaîne d'activité différente sur 1 000
      (motifs, horaires et lieux compris) que la v5 archivée.
- [x] L'onglet 🔁 Campagne affiche l'avancement, le temps avant renouvellement, et les échecs.
- [x] `docs/arch/plateforme-experiences.md` (§ 6 sexies) et `docs/arch/dashboard.md` sont à
      jour ; `docs/changelog.md` porte l'entrée.
- [ ] Le § 4.3 de l'article justifie l'anglais avec les références du § 1.3 **et** énonce les
      réserves du même paragraphe. *(Soumis au verrou de l'article.)*

---

## 9. Arbitrages rendus le 2026-09-14

| # | Question | Décision |
|---|---|---|
| Q1 | Régénérer la population ? | **Oui**, et la v5 part à l'archive froide. Les enrichisseurs doivent produire de l'anglais (C-1b) — sinon la v6 reproduit le problème. |
| Q2 | Quelles expériences rejouer ? | **Les 10 à décideur LLM.** Les 14 témoins déterministes ne lisent aucun prompt ; ils ne sont rejoués que si la v6 change les chaînes d'activités (garde D-7). |
| Q3 | Renforcer le cadrage territorial ? | **Non.** Une seule variable change, l'écart reste attribuable. Le biais occidental relevé par Soegeng (2026) n'est donc pas contré — à déclarer au chapitre 8. |
| Q4 | Quelle portée de traduction ? | **Tout**, les 22 variantes comprises, y compris celles qui ne servent plus. |

| Q5 | Qui traduit ? | **Claude**, dans une session dédiée. Conséquence directe pour le [ticket 069](ticket_069_declaration_usage_ia_et_annexe_meta_prompts.md) : l'annexe de déclaration d'usage des IA doit porter la traduction des prompts, avec la date, le modèle et la version française d'origine. Les deux versions sont publiées côte à côte. |

**Aucune question n'est ouverte.** Le ticket est exécutable en l'état.

---

## 10. Avancement au 2026-09-14

| Lot | État | Ce qui reste |
|---|---|---|
| **A** — archive froide | ✅ **fait** | — |
| **B** — traduction | ✅ **fait** | — |
| **C-1** — cohorte v6 | ✅ **fait** | — |
| **C-1b** — enrichisseurs | ✅ **fait** | — |
| **C-2** — scellement v6 | ✅ **fait** | — |
| **C-3** — `experiments.yaml` | ✅ **fait** | — |
| **C-4/5/6** — renommage | ✅ **fait** | — |
| **D** — pipeline de campagne | ✅ **fait** | — |
| **E** — onglet 🔁 Campagne | ✅ **fait** | — |

### Lot A — fait

`archive/2026-09-14_avant_bascule_anglaise/` : 503,3 Mo, `MANIFEST.yaml` avec les `sha256`.
Les surfaces suivies par git sont **copiées**, le substrat non suivi est **déplacé** — une copie
laisserait le dispositif continuer de le lire. Garde unique dans
`services/llm-agents/experiences/froid.py` : tout chemin dont les segments contiennent `archive`
est refusé, avec ce qu'il faut pour lever le refus. 12 tests
(`scripts/tests/test_074_archive_froide.py`).

### Lot B — fait

22 variantes traduites dans `prompts.yaml`, chacune portant `_ancien_nom`, `_traduction` et un
`_neutralite` **refait après traduction** (le sceau porte sur le `sha256` du texte : traduire le
périme). Verdicts : 8 conformes, 11 conformes avec réserve, 3 non conformes — les mêmes qu'avant,
la traduction ne change pas la conformité. Gabarits, schémas de sortie, descriptions d'itinéraire,
récit de persona et bulletin météo suivis. 9 tests (`test_074_prompt_sans_francais.py`).

**Deux surfaces trouvées hors inventaire, toutes deux silencieuses si manquées :**

- `weather_loader._SNOW_RE` / `_RAIN_RE` reconnaissaient la pluie et la neige sur des mots
  **français**. Sur la table anglaise (`Condition_EN`), elles n'auraient rien reconnu : « No
  precipitation expected » tous les jours de l'année, sans une ligne de journal. Vérifié sur les
  365 jours réels.
- `simulation_controller._agenda_lines` composait `— {label} prévu`. Ce suffixe entre dans
  `Transit.step_label`, que le cache OTP mémorise **sérialisé** : sans bump de `terminal_time`
  (tt4 → tt5), la v6 aurait hérité d'en-têtes anglais sur des sous-étapes françaises.

### Lot C — fait

**C-1b (enrichisseurs) est fait**, et c'est ce qui rend la v6 possible : `main_occupation`,
`personal_bike`, `residence_zone` et `housing_type` sont produits en anglais à la source, pas
corrigés à l'affichage. La clé de `housing_type` reste française (`individuel_isole`) — c'est
un identifiant de jointure ; seul le libellé bascule.

**C-1 (la cohorte)** : les neuf étapes ont tourné, et `data/population/population_1000_AAMAS_v6`
est scellée — `sha256 412efada…`, 13 marges conformes, 0 à corriger, 0 non mesurable, le même
verdict que la v5.

**La v6 EST la v5, en anglais.** Vérifié agent par agent contre l'archive froide :

| | v5 (archivée) | v6 (scellée) |
|---|---|---|
| `person_id` | 1 000 | les **mêmes** 1 000 |
| ménages | 499 | 499 |
| chaînes d'activités (motif + horaires + lieux) | — | **0 différence sur 1 000** |
| descente | 347 échanges, 3 passes, 60,98 → 3,50 pt | **à l'identique** |
| mobiles / déplacements | 894 / 3 299 | 894 / 3 299 |

Six champs seulement diffèrent : `main_occupation`, `housing_type`, `personal_bike` (1 000
chacun), `travel_purposes` (700 — les 300 autres sont vides), `residence_zone` (637 — les 363
« Toulouse » ne changent pas de nom) et `name` (1 000, désormais tiré d'une graine par
`person_id` au lieu de l'horloge).

Il a fallu **trois passes** pour y arriver, et les deux premières sont instructives : elles
ont produit une cohorte plausible et fausse. Voir ci-dessous.

### Trois jointures cassées par la bascule, et comment elles se sont vues

Aucune des trois n'a levé d'erreur. Toutes se sont vues **par un chiffre qui a bougé** dans le
journal de sélection — c'est le seul filet qui a fonctionné, et il ne doit pas rester le seul.

| Où | Ce qui joignait | Ce que ça donnait |
|---|---|---|
| `reference_marges.logement_label` | libellé FR du persona vs liste FR | toute la v6 dans « Autres » — une modalité **publiée**, donc pas une valeur manquante : écart de 99,64 pt sur une ligne |
| `equipment_propensity.design_vector` | `main_occupation` vs `occ_Travail à plein temps` | **toutes** les indicatrices à zéro = modalité de référence pour 100 % de la cohorte ; `permis_adultes` 2,52 → 5,23 pt, `abonnement_tc` 2,65 → 8,45 pt |
| `bike_ownership.propensity_design` | idem | même mécanisme sur la loi d'équipement vélo |

Les trois artefacts (`driving_license.json`, `pt_subscription.json`, `bike_ownership.json`) sont
**gelés** : le nom de leurs variables fait partie de l'ajustement, et les cohortes scellées citent
leur `sha256`. C'est donc la LECTURE qui traduit, par `population_reference.occupation_enquete`,
qui connaît les deux vocabulaires. Une modalité qu'aucun des deux ne connaît tombe toujours dans
la référence — c'est le bon repli — mais elle lève désormais une `[ALARME]`, une fois par valeur.

`packages/mobility_core/tests/test_074_vocabulaire_lois_ajustees.py` (24 tests) vérifie que le
vecteur de design est **identique** dans les deux langues *et* que l'indicatrice attendue vaut 1 :
un vecteur identique mais tout à zéro des deux côtés passerait le premier contrôle sans rien
prouver — c'est exactement le piège.

**Preuve que c'est réparé** : la sélection v6 reproduit la v5 au chiffre près — 347 échanges en
3 passes, perte 60,98 → 3,50 pt, les dix marges identiques à la décimale, les mêmes 1 000
`person_id`, les mêmes 499 ménages, 0 chaîne d'activité différente. Seuls diffèrent les six
champs traduits et les prénoms, désormais tirés d'une graine.

### Une quatrième, hors vocabulaire : la reprise perdait la sélection

`executer_generation.py --de 4` repartait d'un espace de noms neuf, donc sans le
`POPULATION_TAG` que l'étape 3ter avait posé — et `pop_filename()` rendait le nom du **vivier**.
L'étape 4 s'est mise à router 33 420 paires au lieu de 3 258, et l'étape 7 aurait exporté le
vivier de 10 000 sous le nom de la cohorte de 1 000. L'état est maintenant consigné après 3ter
et relu à la reprise ; sans lui, l'outil **refuse** au lieu de deviner.

### Lots D et E — faits, et trois choses que le ticket n'avait pas vues

**La campagne porte 22 expériences, pas 10.** Le ticket écartait les 14 témoins déterministes
parce qu'ils ne lisent aucun prompt — ce qui est juste. Mais il a été écrit avant que le lot A
ne vide la plateforme : **leurs résultats ne vivent plus que dans l'archive froide**, que la
doctrine interdit de référencer. Ne rejouer que les 10 bras LLM aurait donné des scores sans
rien en face. Ils sont gratuits (aucun appel LLM) et passent en première phase. La sonde
`escort66` (2 expériences) est écartée : hors protocole, décision du 2026-09-14.

**Les définitions ont dû être recréées, pas rejouées.** `data/experiences/` était vide.
`scripts/migrations/definir_experiences_v6.py` LIT les YAML archivés comme **spécification**
(températures, graines, tolérances) et ÉCRIT des définitions neuves — cohorte v6, jeu v6, noms
de variantes traduits lus dans `_ancien_nom`. Rien n'est copié depuis l'archive, et
`executions_connues` repart vide : la v6 n'a pas d'histoire. Les 22 sont validées par la
plateforme elle-même (`experiences definir`, schéma strict et nom calculé).

**L'archive froide n'était pas froide — un montage Docker suit l'inode, pas le nom.**
Le lot A *déplace* `data/experiences/` et `data/jeux/`. Les conteneurs déjà démarrés ont
continué de lire leurs 26 définitions et d'écrire dans les dossiers déplacés, c'est-à-dire
**dans l'archive**. Le garde de `froid.py` ne pouvait rien voir : il inspecte des chemins, et le
conteneur ne voit que `/app/data/…`. Constaté en construisant le jeu v6, qui a écrit 2 Mo dans
l'archive. Corrigé : le script d'archivage redémarre `controller`, `api` et `worker` dès qu'il
déplace quelque chose, et le dit ; fail-open, avec la commande à lancer à la main si Docker
manque.

**Et un quatrième, sur le nommage.** Les noms d'expériences étaient tronqués en silence à 64
caractères, perdant leur queue — `nosim`, `noret`, `nochn` : les segments qui disent ce que la
mesure a coupé. Mesuré sur la campagne v6 : 12 noms sur 22 tronqués, 2 réduits au même nom.
`LONGUEUR_MAX` passe à 128, et `dashboard.campagne.libelle()` rend chaque nom lisible **depuis
sa définition** plutôt qu'en le redécoupant.

**Ce qui n'a PAS été lancé.** Aucune expérience. Les 22 définitions existent et sont validées ;
le lancement est laissé à l'auteur (décision du 2026-09-14 : préserver le quota de jetons).

### Ce que la bascule a appris sur le dépôt

- **Une substitution de vocabulaire ne se fait pas par fichier entier.** `car`, `work` et `other`
  sont à la fois des mots de prose et des étiquettes de mode relues dans le texte du prompt par
  `parse_option_modes`. Une passe globale a produit 37 129 remplacements avant d'être défaite.
  La traduction se fait **trait par trait, à une frontière nommée**.
- **Un test qui recopie la production ne mesure que lui-même.**
  `test_personal_bike._include_bike` répondait encore « vélo autorisé » à un champ absent — le
  défaut d'avant le ticket 015 — et ne connaissait que le français : il aurait laissé passer une
  cohorte v6 entière sans jamais tomber. Il importe désormais `_owns_bike`.
- **La vacuité se déguise en perfection.** Une cible jointe anglaise lue contre un fichier
  français ne trouve aucune ligne, et un contrôle naïf rend alors un écart de 0. Les politiques
  ajustées ont reçu la même garde : au-delà de 40 % d'une catégorie tombée dans `__missing__`,
  `[ALARME]`.
