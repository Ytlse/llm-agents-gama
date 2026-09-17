# Ticket 076 — Ce qu'une comparaison de bras doit publier, et les six bras payants du prompt minimal

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-14.
>
> **Catégorie** : Modélisation Statistique (📊) / Plateforme (🛠️)
>
> **Hérite du [ticket 045](ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md)**,
> clos le 2026-09-14 : le substrat unique est livré, la reconstruction est faite, et ce qui n'y
> a pas été exécuté vit ici. Le 045 ne rouvre pas.
>
> **Touche** : les sorties de synthèse et de comparaison, l'IHM de lancement du tableau de bord,
> et — pour le seul lot 3 — le budget d'appels aux modèles.
>
> **✅ CLOS LE 2026-09-15, décision de l'auteur** — voir le
> [§ 8](#8-clôture-le-2026-09-15). Lots 1 et 2 constatés clos (livrés le 2026-09-11 par le 045).
> Lot 3 : le canal Antigravity est **disqualifié** (température non réglable), `mistral-small-latest`
> est **abandonné**, `mistral-large-2512` est **fait**, les deux bras Gemini sont **relancés et
> comptés terminés**. Les § 0 à 6 sont conservés tels qu'écrits le 2026-09-14 ; le § 7 est la
> relecture qui a précédé la clôture.

---

## 0. Point de départ

**Ce que le 045 a livré** (2026-09-11, ne pas re-chercher) : la cause racine du substrat
divergent est fermée, la base v1 est archivée, la journée se referme (3 299 déplacements attendus
au lieu de 2 405), le jeu de déplacements a été construit et les **14 exécutions gratuites du 2×2
chaîne / anticipation ont tourné** — zéro défaillance de moteur, les choix forcés vont de 279 à
811 selon le bras chaîne active, contre 44 pour tous chaîne coupée.

**Ce qui restait, et qui fait ce ticket :**

| Lot | Règle d'origine | Coût |
|---|---|---|
| **1** | R10, R11, R12 — ce qu'une comparaison publie | gratuit, aucun appel de modèle |
| **2** | R19 — l'empreinte de population au lancement | gratuit, IHM |
| **3** | Lot 4c du 045 — six bras `prompt_minimal` | **payant**, sur GO explicite |

**Deux faits ont changé le terrain entre l'écriture de ces règles et aujourd'hui**, et ils
commandent l'ordre d'exécution :

1. **La référence est la v6, pas la v5.** La bascule anglaise ([ticket 074](ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md))
   a scellé `population_1000_AAMAS_v6`, qui reproduit la v5 au chiffre près — mêmes 1 000
   personnes, mêmes 499 ménages, mêmes chaînes d'activités. Seuls six champs de langue changent.
2. **Le jeu et les exécutions du 11 septembre sont à l'archive froide.** `data/jeux` et
   `data/experiences` sont **vides**, et le code refuse de résoudre l'archive aux trois points de
   passage (cohorte, jeu, prompt). Les mesures du 2×2 restent auditables dans
   `archive/2026-09-14_avant_bascule_anglaise/`, mais la plateforme ne les sert plus.

**Conséquence :** le lot 3 n'est pas lançable tant que le **jeu v6** n'est pas construit et que le
**lot D du 074** (pipeline de campagne) n'est pas livré. Les lots 1 et 2, eux, ne dépendent de
rien : ils changent ce qu'une synthèse écrit, pas ce qu'elle mesure.

---

## 1. Lot 1 — ce qu'une comparaison de bras publie (gratuit)

Reprises telles quelles de `specs/ticket_045/substrat-unique-v5.md`, bloc D. Les trois règles
tiennent ensemble : publier des parts sans dire combien de décisions n'en étaient pas est ce qui
a fait croire à neuf points d'écart entre familles statistiques là où il n'y avait que de la
contrainte de chaîne.

**R10.** Une synthèse publie les parts modales **des deux façons** : toutes décisions, et hors
décisions à itinéraire unique. Les deux jeux de chiffres portent leur effectif.
*Test :* les deux blocs existent, et leurs effectifs diffèrent du compte de choix forcés.

**R11.** Le compte de choix forcés par bras est publié à côté de ses parts. Le compteur existe
déjà (`compteurs.choix_unique`) : il est **remonté, pas recalculé**.
*Test :* la valeur publiée égale `compteurs.choix_unique`.

**R12.** La comparaison terme à terme entre bras se fait sur l'**intersection** des déplacements
que tous ont réellement décidés, et le périmètre retenu est déclaré avec le chiffre.
*Test :* comparer trois bras rend un périmètre commun, et ce périmètre est écrit dans la sortie.

**Pourquoi ça compte maintenant :** le [ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md)
audite précisément la double lecture. Il a besoin que les deux lectures soient publiées pour
statuer — ce lot est son outil, pas son doublon.

---

## 2. Lot 2 — l'empreinte de population au lancement (gratuit)

**R19.** L'empreinte de la population s'affiche **à côté du bouton de lancement**, pas seulement
dans la synthèse écrite après coup.
*Test :* revue de l'IHM (`scripts/dashboard/app.py`).

La garde de cohérence population / jeu (**R20**, `jeu.py:638`) existe et compare les empreintes,
pas les noms : elle reste en place, cette règle-ci ne la remplace pas. R19 rend visible **avant**
le lancement ce que la garde refuserait **pendant** — c'est tout son intérêt après un changement
de cohorte.

---

## 3. Lot 3 — les six bras `prompt_minimal` (payant, sur GO explicite)

Un bras par modèle ayant produit une mesure complète en v1. Tous à `temperature: 0.0`,
`top_p: 1.0`, `max_tokens: 4096`.

| Modèle | Accès | Mesure v1 de référence | Réglage | Définition sur disque |
|---|---|---|---|---|
| `claude-opus-4.6` | antigravity | complète sous `prompt_minimal` | attente 600 s | **aucune — à créer** |
| `gemini-3.8-flash` | antigravity | complète sous `prompt_minimal` | attente 120 s | existe (archivée, v5) |
| `gemini-3.5-flash-lite` | passerelle | complète sous `prompt_minimal` | attente 120 s | existe (archivée, **ancienne population**) |
| `gemini-3.1-flash-lite` | passerelle | complète sous `prompt_minimal` | attente 120 s | existe (archivée, **ancienne population**) |
| `mistral-large-2512` | passerelle | complète sous `prompt_minimal` | attente 120 s | **aucune — à créer** |
| `mistral-small-latest` | passerelle | complète, mais sous `minimal_persona` (invalidé) | attente 120 s | **aucune — à créer** |

`mistral-small-latest` n'a jamais été mesuré sous le prompt minimal en service : son bras est
**neuf**, pas une répétition. `gemini-3.1-flash-lite-preview` est écarté (décision de l'auteur,
11 septembre) — seul le modèle stable est retenu.

**Recouvrement avec la campagne du 074, à ne pas jouer deux fois.** Les trois bras Gemini sont
déjà dans les dix expériences que le 074 rejoue en v6. Le lot 3 ne les redemande pas : il
**ajoute** les trois modèles absents du registre (Claude, les deux Mistral) et vérifie que les
trois autres sont bien passés par la campagne.

**Prérequis, dans l'ordre :** jeu v6 construit → lot D du 074 livré → estimation de coût
(`make experience-estimer`) → **GO explicite de l'auteur**. Aucun appel de modèle avant ce GO.

---

## 4. Ordre d'exécution

1. **Lot 1** (R10-R12) — sans dépendance, et débloque l'audit du 057.
2. **Lot 2** (R19) — sans dépendance ; d'autant plus utile que la cohorte vient de changer.
3. **Lot 3** — après le jeu v6 et le lot D du 074, sur GO.

---

## 5. Critères d'acceptation

- [x] Une synthèse de comparaison publie les deux lectures avec leurs effectifs (R10) —
  **livré le 2026-09-11** par le 045, `test_045_07_choix_forces.py` vert le 2026-09-15.
- [x] Le compte de choix forcés par bras est publié et égale `compteurs.choix_unique` (R11) —
  idem, relayé et non recalculé (`registre.py`).
- [x] Une comparaison à trois bras déclare son périmètre d'intersection avec le chiffre (R12) —
  idem, `perimetre_commun()` et `test_r12_le_perimetre_commun_est_lintersection_des_decisions_reelles`.
- [x] L'empreinte de population est lisible à côté du bouton de lancement (R19) — **code livré le
  2026-09-11** (`_bandeau_substrat`, branché au-dessus des boutons) ; constaté clos par l'auteur
  le 2026-09-15.
- [x] La garde R20 (empreintes, pas noms) est toujours verte — non-régression. Garde en place
  (`Jeu.verifier_population`, `jeu.py:919`) ; constaté clos par l'auteur le 2026-09-15.
- [x] Lot 3 — **requalifié à la clôture** (§ 8) : deux bras Antigravity disqualifiés, Mistral
  Small abandonné, Mistral Large fait, les deux Gemini relancés et comptés terminés. Plus rien
  à lancer depuis ce ticket, donc plus rien à estimer.

---

## 6. Questions ouvertes

- **Les six bras se jouent-ils sur la v6 seule, ou faut-il une passerelle vers les mesures v1 ?**
  Les mesures v1 de référence portent une autre population et une autre langue : les comparer
  terme à terme n'est pas défendable. Par défaut, ce ticket ne compare qu'à l'intérieur de la v6.
- **Les 14 témoins déterministes, qui ne lisent aucun prompt, sont-ils rejoués sur la v6 ?**
  La garde D-7 du 074 ne l'impose pas (chaînes d'activités identiques), mais leurs exécutions
  sont à l'archive froide et ne sont plus servies. Les rejouer ne coûte aucun appel de modèle.
  Question portée par le 074, rappelée ici parce que le lot 3 en dépend pour être apparable.

---

## 7. Avancement au 2026-09-15 — relecture contre le code

**Le § 0 était faux sur deux points et périmé sur deux autres.** Relu le 2026-09-15 contre le
code, les tests, la spec du 045 et les exécutions présentes sur disque.

| Lot | État réel | Preuve |
|---|---|---|
| **1** — R10-R12 | ✅ **livré le 2026-09-11 par le 045**, trois jours avant l'ouverture de ce ticket | `experiences/registre.py` : `parts_modales_hors_choix_unique`, `choix_forces` relayé de `compteurs.choix_unique`, `perimetre_commun()` (l. 589) servi par `make comparer` ; `tests/test_045_07_choix_forces.py`, **10 tests verts** le 2026-09-15 (dont `test_r10_…` et `test_r12_le_perimetre_commun_est_lintersection_des_decisions_reelles`) ; changelog du 2026-09-11, « Les parts modales se publient maintenant des deux façons » |
| **2** — R19 | ✅ **livré le 2026-09-11 par le 045** | `scripts/dashboard/experiences.py:391` `_bandeau_substrat`, appelé l. 4371 juste au-dessus des boutons : empreinte d'identité et de contenu, nom du jeu, alerte « substrat non scellé », refus `coherence_population_jeu` **avant le clic** ; changelog du 2026-09-11, « Le substrat s'affiche avant le lancement ». La revue visuelle de l'IHM n'a pas été refaite ici. |
| R20 | ✅ garde en place | `Jeu.verifier_population` (`jeu.py:919` — plus l. 638, le fichier a bougé) compare les empreintes, pas les noms |
| **3** — six bras | ⏳ **prérequis 1 et 2 levés**, bras dans l'état du tableau suivant | jeu v6 `data/jeux/population_1000_AAMAS_v6_20260316_EN` (sceau `412efada…`) ; lots D et E du 074 livrés le 2026-09-15 ; campagne `multimodeles_v6` terminée le 2026-09-15 à 20:32 UTC — 19 faites, 4 échouées sur quota |

La table « État au 2026-09-11 » de `specs/ticket_045/substrat-unique-v5.md` disait déjà
**livré** pour le bloc D (R10-R12) et le bloc F « R19 comprise ». La note de clôture du 045
(2026-09-14) les a listés comme non exécutés ; ce ticket en a hérité l'erreur. **Rien à coder
pour les lots 1 et 2** : il reste à l'auteur de les constater clos.

### Lot 3 — les six bras, un par un, sur la v6

| Modèle | Définition v6 | Exécution `prompt_minimal_02` | Ce qui change |
|---|---|---|---|
| `claude-opus-4.6` | ✅ créée (`exp_agy-claude-o-4-6_promin02_…`) | aucune | Canal **Antigravity** : règle **P2** de `specs/decideur-antigravity.md` — **aucune part modale publiable**, mesure de coût nul. Retiré de la campagne le 2026-09-15. Ne peut être qu'un banc d'essai. |
| `gemini-3.8-flash` | ✅ existe (`exp_agy-gemini-38-f_promin02_…`) | 1 lancement le 2026-09-15 à 04:49, **0 sollicitation** en 325 s, non clos | Même canal Antigravity, même règle P2 : **non publiable**. |
| `gemini-3.5-flash-lite` | ✅ existe (`exp_gemini-35-fl_promin02_…`) | aucune — **échec de campagne** : « lancée 3 fois sans jamais écrire d'état » (le défaut `promin02` noté au 074) | À diagnostiquer avant tout relancement ; le prompt calibré du même modèle a tourné quatre fois sans ce défaut. |
| `gemini-3.1-flash-lite` | ✅ existe (`exp_gemini-31-fl_promin02_…`) | 1 exécution le 2026-09-15 à 14:48, **48 sollicitations**, 9 interruptions, non close — **quota épuisé** (500/500 requêtes/jour) | Se reprend au renouvellement du quota (repêchage de campagne ou `experience-reprendre`). |
| `mistral-large-2512` | ✅ créée (`exp_mistral-l-25_promin02_…`) | ✅ **terminée** le 2026-09-15 à 18:00 — 2 618 sollicitations, 545 choix uniques, 0 erreur | Jouée par la campagne `multimodeles_v6` (tickets 055 / 080), phase « quota gratuit », sans GO de ce ticket. **Fait.** |
| `mistral-small-latest` | ❌ aucune | — | Toujours à créer (slug `mistral-s`, spec `nommage-canonique-experiences`). Seul bras du lot entièrement à faire. |

**Ce que ça change pour le lot 3 :**

1. **Le lot n'est plus « payant » au sens strict.** Les quatre bras passerelle sont en phase
   `llm_gratuit` de la campagne (« aucun ne coûte d'argent »), et le canal Antigravity est
   « mesure de coût nul » (P2). L'estimation `make experience-estimer` reste due par principe,
   mais le GO porte sur du quota, pas sur de l'argent.
2. **Deux bras sur six ne produiront jamais de part modale publiable** (Claude, Gemini 3.8 —
   canal Antigravity, règle P2). À trancher par l'auteur : les garder comme banc d'essai, ou les
   sortir du lot. En l'état, « six bras » veut dire **quatre mesures**.
3. **Un bras est fait** (Mistral Large), **deux sont à reprendre** (Gemini 3.1 : quota ;
   Gemini 3.5 : défaut de lancement à diagnostiquer), **un est à créer** (Mistral Small).
4. « Ne pas jouer deux fois » est réglé par construction : la campagne saute les expériences
   `terminee`.

### Questions du § 6 et héritages du 045

- **Six bras sur la v6 seule** : toujours la position par défaut, rien ne l'a contredit.
- **Les 14 témoins déterministes ont été rejoués sur la v6** par la campagne (phase `temoins`,
  14 faites) : question close, la comparaison LLM / témoin a de nouveau quelque chose en face.
- **`ratios_du_plan()` rendait toujours `None`** : corrigé le 2026-09-11 (Q3 de
  `specs/ticket_045/questions.md` — chemin du plan, absence journalisée, plan monté en lecture
  seule dans le conteneur). Ce ticket n'a rien à en reprendre, malgré ce que dit la note de
  clôture du 045.
- **Règle 1 du contrat d'évaluation** (« les mêmes 21 variables », fausse) : portée par le
  [ticket 046](ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md), toujours « à
  faire ». Hors de ce ticket.

### Ce qu'il reste à ce ticket, en clair

1. Que l'auteur constate les lots 1 et 2 **clos**, livrés par le 045 (revue visuelle de R19
   incluse).
2. Trancher le sort des deux bras Antigravity (banc d'essai, ou sortie du lot).
3. Définir `mistral-small-latest` sur la v6.
4. Reprendre Gemini 3.1 et diagnostiquer Gemini 3.5 en `promin02`.
5. Publier l'estimation, puis **GO**.

Le statut dans `tickets_status.yaml` n'a pas été changé par cette relecture : c'est à l'auteur.

---

## 8. Clôture le 2026-09-15

**Décisions de l'auteur**, rendues à la lecture du § 7 :

1. **Lots 1 et 2 : clos.** Livrés le 2026-09-11 par le 045 ; ce ticket n'y a rien ajouté.
2. **Le canal Antigravity est disqualifié** pour toute mesure : la température n'y est pas
   réglable (règle **P2 bis** de `specs/decideur-antigravity.md` — les réglages d'échantillonnage
   ne sont pas garantis, une réponse muette compte comme un trou et jamais comme « température
   0 »). Un bras qui ne peut pas se réclamer du protocole « tous les modèles à température nulle »
   ne peut pas entrer dans une comparaison de bras. `claude-opus-4.6` et `gemini-3.8-flash`
   **sortent du lot 3**. Leurs définitions restent sur disque, comme banc d'essai de la mécanique,
   ce que P2 leur reconnaît.
3. **`mistral-small-latest` est abandonné** : inutile. Aucune définition n'est créée.
4. **`mistral-large-2512` est fait** — exécution `prompt_minimal_02` terminée le 2026-09-15 à
   18:00, 2 618 sollicitations, 0 erreur, jouée par la campagne `multimodeles_v6`.
5. **`gemini-3.1-flash-lite` et `gemini-3.5-flash-lite` en `prompt_minimal_02` : relancés le
   2026-09-15 et comptés terminés** par l'auteur. Au moment de la relecture (§ 7, 20:32 UTC), le
   premier était arrêté sur quota épuisé et le second n'avait jamais écrit d'état ; l'auteur les a
   relancés dans la soirée. Leur clôture effective se lit dans la campagne du
   [ticket 074](ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md), qui les porte
   depuis l'origine (le § 3 l'écrivait : « le lot 3 ne les redemande pas »).

**Bilan du lot 3 tel que clos :** sur six bras prévus, trois sont mesurés ou en cours de mesure
(Mistral Large fait, Gemini 3.1 et 3.5 relancés), deux sont disqualifiés (Antigravity), un est
abandonné (Mistral Small). Plus rien à lancer depuis ce ticket, donc pas d'estimation de coût ni
de GO à donner.

**Ce ticket ne rouvre pas.** Ce qui vit encore vit ailleurs : l'aboutissement des deux bras Gemini
dans la campagne du 074, la règle 1 du contrat d'évaluation au 046.
