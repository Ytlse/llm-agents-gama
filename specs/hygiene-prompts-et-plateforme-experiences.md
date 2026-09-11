# Hygiène des prompts et remise en ordre de la plateforme d'expériences

Plan d'exécution — v3 du 2026-09-10, arbitré et **partiellement livré** (§2, §4.1). Le reste attend
validation ; aucun fichier d'expérience n'a été déplacé ni supprimé.

Deux contraintes posées par l'auteur, structurantes pour tout le document :

- **Aucune suppression définitive.** On archive, les données restent sur le disque.
- **La règle dépend de la famille du prompt** (§1.1). La v1 de ce plan jugeait les prompts
  experts avec les critères du minimal et signalait à tort une dizaine de variantes. Corrigé.

---

## 1. Doctrine et constat

### 1.1 Deux familles, deux règles — c'est le fondement

| Famille | Ce qu'on attend | Ce qui est interdit |
|---|---|---|
| **Minimale** — **`prompt_minimal`, et lui seul** | le strict minimum : la tâche, le format de sortie, rien d'autre | **tout élément susceptible d'influencer un mode plutôt qu'un autre**, quelle qu'en soit la forme |
| **Experte / calibrée** (toutes les autres, `b_min` compris) | nommer les modes et les cadrer est **volontaire** — c'est l'objet même de ces prompts | **règles figées** (« sous tel seuil, choisir telle option ») et **formules mathématiques** |

Corollaire tranché par l'auteur : ajuster un prompt expert sur l'écart à CEREMA puis le noter
sur le même jeu **est l'objectif de la calibration de prompt**, pas un défaut. Ce plan ne pose
donc aucune règle de séparation calibration / mesure.

**Tranché le 2026-09-10 — et livré.** La famille ne se devinait pas ; elle est désormais
déclarée en tête de `prompts.yaml` :

```yaml
familles:
  minimale:
  - prompt_minimal
  defaut: experte
```

Un seul prompt minimal, tout le reste expert. `b_min` rejoint donc la famille experte.

### 1.2 Violations réelles — trois, pas dix

**V1 — `minimal_persona`, famille minimale, consigne de sortie n° 4 :**

> *« Justifie la répartition en une phrase concise, en précisant si c'est le cas pourquoi la
> **marche** n'obtient pas la plus forte probabilité. »*

Un mode nommé, avec une présupposition sur son rang, dans un prompt dont toute la raison d'être
est de n'influencer aucun mode. C'est le seul manquement de la famille minimale — `b_min` est
propre.

*Origine* : commit `0bc68b7`, 2026-06-13, « update prompt ». Forme initiale : *« …pourquoi la
marche n'est pas le meilleur choix **et si tu as hésité** »*. Le « si tu as hésité » dit
l'intention : **c'était une aide au débogage**. Le fragment de débogage a été retiré ; la
présupposition est restée, et a été reprise telle quelle à la création de `minimal_persona` le
2026-09-06, alors que son parent déclaré `b_min` ne la portait pas.

**V2 — `calibrated_20260612_1949`, règle figée seuil → mode :**

> *« **Pour les trajets inférieurs à 500 mètres**, présente systématiquement la marche comme le
> mode par défaut privilégié »*

**V3 — `calibrated_20260613_1410`, règle figée seuil → mode :**

> *« considération systématique de la marche pour les **segments ≤ 1 km** comme option de
> premier ordre »*

**Aucune formule mathématique dans aucune des 24 variantes.**

### 1.3 Deux nombres — tranchés : cadrages acceptables

- **« Applique la règle des 48 heures »** — 10 variantes, dont toute la famille `expert_chaine`.
- **« Entre 3 et 25 °C sans précipitation, c'est le temps ordinaire »** — m5, m6, m7.

**Décision de l'auteur (2026-09-10) : cadrages acceptables.** Aucun des deux n'associe un seuil
à un mode. Ils ne tombent pas sous C1, et **les runs `expcha*` restent valides**. C'est la
jurisprudence que l'auditeur applique : un nombre qui qualifie une situation est un cadrage ;
un nombre qui désigne un mode est une règle.

Tout le reste de ce que la v1 signalait — « Pour la marche, insiste… », « Pour le vélo,
transforme sa perception… », « privilégier les modes assis pour les personnes âgées », « la
marche est le mode préférentiel des aînés », « accident de vélo en l'absence de pistes
cyclables » — **est conforme** : ce sont des cadrages modaux délibérés dans des prompts
experts. Retiré du périmètre.

### 1.4 Templates — le vrai angle mort

Les templates sont **partagés par toutes les familles**. Un déséquilibre qui y vit s'applique
donc aussi sous prompt minimal, où rien ne doit influencer un mode. C'est là que se joue la
neutralité du témoin, et personne ne l'a auditée.

**Le précédent existe déjà, documenté et chiffré** (`simulation_controller.py:320`) :

> *« La position des véhicules n'est PLUS énoncée dans le prompt : la formulation (« votre vélo
> est avec vous ») agissait comme une invitation et a **gonflé la part vélo de +5,5 points**
> (mesure EMC², run 2026-08-19_13_17). »*

Autrement dit : une ligne purement informative du template utilisateur — qui disait seulement à
l'agent où se trouvait son vélo — a suffi à déplacer la part vélo de 5,5 points. Elle a été
retirée et la règle de chaîne déplacée dans le prompt système. **C'est exactement la même
classe de problème que V1**, déjà rencontrée, mesurée et corrigée une fois. Les deux points
ci-dessous n'ont pas eu droit au même examen :

- **T1 — `travel_plan_describe_v2.j2`, ligne `Distance` asymétrique.** Elle est rendue pour les
  options directes (marche, vélo, voiture, car scolaire) et **absente des options transports
  collectifs multi-jambes**. Un mode dont la distance n'est jamais affichée n'est pas comparé
  sur la même base que les autres.
- **T2 — `travel_plan_describe_v2.j2`, mention de gratuité asymétrique.** `Car scolaire liO
  **(gratuit)**` est la seule mention de coût de tout le rendu, alors que la marche et le vélo
  sont gratuits eux aussi.
- **T3 — `stm_reflection/template.md.j2`, exemples à valence** (« Le bus 69 est fiable »,
  « Long temps d'attente pour le Bus 20 »). **Sans effet sur les expériences en cours**
  (`memoire: false` partout) ; bloquant avant tout run avec mémoire.

Le template `itinary_multi_agent.md.j2` est par ailleurs **propre** : aucun a priori modal.

---

## 2. Invalidation des prompts (point 2)

### 2.1 Principe : marquer, jamais éditer ni retirer

Corriger la clause **dans** `minimal_persona` changerait silencieusement l'identité de huit
expériences déjà mesurées : même nom, même `signature()`, deux textes différents. C'est le trou
N10 signalé au §7.1 de `specs/decideur-antigravity.md`. Donc :

1. **Aucune variante existante n'est éditée ni retirée de `prompts.yaml`.**
2. Chaque variante fautive reçoit un bloc `_invalidation` :

```yaml
minimal_persona:
  content: |-
    …inchangé…
  famille: minimale            # nouveau champ, cf. §4.1
  _provenance: {…inchangé…}
  _invalidation:
    statut: invalide
    le: '2026-09-10'
    regle: M1                  # cf. grille §4.2
    motif: >-
      Famille minimale : la consigne de sortie n° 4 nomme la marche et présuppose son rang.
      Introduite en débogage (commit 0bc68b7, 2026-06-13), jamais retirée.
    remplace_par: prompt_minimal
```

3. ✅ **livré** — `PromptManager.get_system_prompt()` et `render()` **refusent** une variante
   `invalide` (`VariantePromptInvalide`, sous-classe de `ValueError`), en nommant la règle et le
   remplaçant. Un prompt **actif** invalidé fait échouer `check_category`, donc le démarrage du
   service. Le refus ne vaut que pour le service : `verifier_validite=False` rend le texte sans
   contrôle, et c'est ce que fait `empreinte_gabarit` — une invalidation ne doit pas rendre
   irreproductibles les empreintes scellées. Une exécution lancée sur un gabarit invalidé le
   porte dans son empreinte (`invalide: true`, `invalide_regle`), hors du `sha256`.

   *Reste facultatif* : un `--forcer-prompt-invalide` au niveau du CLI d'expérience. Il n'est
   plus nécessaire au rejeu d'archive, celui-ci ne passant pas par le chemin de service.

### 2.2 Portée exacte

| Variante | Statut | Règle |
|---|---|---|
| `minimal_persona` | **invalide** ✅ posé | M1 (famille minimale, élément influençant un mode) |
| `calibrated_20260612_1949` | **invalide** ✅ posé | C1 (seuil 500 m → marche) |
| `calibrated_20260613_1410` | **invalide** ✅ posé | C1 (seuil ≤ 1 km → marche) |
| les 21 autres | **valides** | Q1 tranchée : 48 h et 3-25 °C sont des cadrages |

`expert_gem_3.8_v1` est déclaré **expert** (« prompt expert light […] dérivé de
`minimal_persona` ») : nommer la marche y est licite. Il reste valide. Seule sa lignée est à
corriger — un enfant déclaré expert ne peut pas revendiquer un parent minimal sans que la
différence de règle soit explicite.

### 2.3 Variante de remplacement — **livrée le 2026-09-10**

Créée **à côté**, sans rien écraser :

| Nouvelle | Famille | Dérivée de | Changement | sha256 gabarit |
|---|---|---|---|---|
| **`prompt_minimal`** | minimale | `minimal_persona` | consigne n° 4 → « Justifie la répartition en une phrase concise. » — rien d'autre, au caractère près | `88f0aefcff9422ae…` |

Vérifié après pose : les 24 textes existants sont **intacts** (sha de contenu identiques), et les
empreintes scellées restent reproductibles — `minimal_persona` rend toujours `8d78a261…`,
`expert_chaine_m6` toujours `3b7f172e…`. 695 tests passent.

Les deux `calibrated_*` invalidées sont des artefacts de campagne de juin, jamais employées en
expérience : **pas de remplaçante**, sauf demande.

### 2.4 Correctifs de template

- **T1** — `Distance` sur toutes les options, ou sur aucune. Préférence : toutes.
  **Différé** : « pas de problème si on a le temps » (auteur, 2026-09-10). Ni bloquant ni oublié.
- **T2** — retirer « (gratuit) », ou l'appliquer à tous les modes gratuits. Préférence : retirer.
- **T3** — exemples sans mode nommé ni valence. Bloquant avant tout run avec `memoire: true`.

⚠ T1 et T2 **changent le texte présenté**, donc l'empreinte de gabarit, donc la frontière de
comparabilité. À livrer d'un bloc, à une date, et à consigner au changelog. Idéalement mesurés
par un rejeu apparié, comme l'avait été la ligne « votre vélo est avec vous ».

---

## 3. Invalidation des expériences (point 3)

### 3.1 Ce qui est concerné ✅ **appliqué le 2026-09-10**

Critère : `gabarit.variante` ∈ {variantes invalidées}. Les deux `calibrated_*` n'ont jamais
servi en expérience ; il ne reste donc que la famille `minper`. **4 invalidées** (une mesure
existe), **16 archivées** (rien de mesuré) — détail au §5 :

| Expérience | Décidés | Statut proposé |
|---|---|---|
| `exp_agy-gemini-38-f_minper_jtir_t0_nosim` | 2 635 | **invalide** ✅ (composite 10,32) |
| `exp_gemini-31-fl_minper_jtir_t0_nosim` | 2 637 | **invalide** ✅ (18,39) |
| `exp_gemini-35-fl_minper_jtir_t0_nosim_2` | 2 637 | **invalide** ✅ (14,84) |
| `exp_mistral-s_minper_jtir_t0_nosim` | 2 635 | **invalide** ✅ (27,44) |
| `exp_qwen38-27b_minper_jtir_t0_nosim` | 244 | archivée ✅ — partielle, aucun score publié |
| `exp_meta-mg_minper_jtir_p1` / `…_t0_nosim_2` | 55 / 10 | archivées ✅ — partielles, sans score |
| `exp_agy-claude-o-46_minper_jtir_t0_nosim` | 8 | archivée ✅ — partielle, sans score |
| `exp_gemma-4-31b_minper_jtir_t0_nosim` | 0 | archivée ✅ — rien mesuré |
| `exp_lgbm_jtir_nosim` | 2 634 | **non concernée** — décideur `modele`, le prompt n'est pas lu |

Les `expcha` / `expcham5` / `m6` / `m7` restent **valides** : famille experte, aucune règle
figée (sous réserve de Q1).

### 3.2 Mécanique — un fichier, aucun déplacement ✅ **livré le 2026-09-10**

`experiences/statut.py` — `actif` / `archivee` / `invalide`, marqueur
`data/experiences/<exp>/statut.json`, motif obligatoire hors `actif`, historique des
transitions empilé, marqueur illisible = `actif`. Branché sur `registre.lister()`
(`inclure_masquees`), `rendu_scores` (bandeau), le tableau de bord (champ `statut` +
`masquee()`), et deux commandes : `make experience-statuts`, `make experience-statuer`.
12 tests de non-régression, dont un qui vérifie qu'**aucun fichier ne disparaît** quand on
pose un statut.

**Distinction d'usage retenue** : `invalide` qualifie une *mesure publiée* (un `scores.json`)
fautive pour une raison nommée ; `archivee` retire du listing ce qui n'a rien mesuré à
défendre. Un `statut.json` type :

```json
{
  "statut": "invalide",
  "le": "2026-09-10",
  "motif": "gabarit minimal_persona invalidé (famille minimale, règle M1)",
  "reference": "specs/hygiene-prompts-et-plateforme-experiences.md#22",
  "donnees": "conservees",
  "visible_par_defaut": false
}
```

- **Rien n'est déplacé, rien n'est effacé.** Les 194 Mo restent en place.
- `registre.lister()` et le tableau de bord masquent par défaut `statut != actif`, avec un
  filtre « inclure archivées / invalidées ».
- `scores.json` **n'est pas retouché** : le chiffre reste lisible, c'est son statut qui change.
- `rendu_scores.py` ajoute un bandeau « mesure invalidée — motif ».

---

## 4. Garde-fou : validation par un agent indépendant (point 4)

### 4.1 Prérequis — déclarer la famille ✅ **livré**

La famille est déclarée en tête de `prompts.yaml` (§1.1) : `minimale: [prompt_minimal]`,
`defaut: experte`. Une variante minimale porte en plus `famille: minimale` dans son entrée.
Sans cette déclaration la grille n'est pas applicable — la même phrase est licite dans une
famille et fautive dans l'autre.

`PromptManager.famille(variante)` rend la famille déclarée. ✅ livré.

### 4.2 La grille du `prompt-auditor` ✅ **livré le 2026-09-10**

Agent **nouveau, lecture seule, distinct de celui qui écrit le prompt**.
`optimiser-prompt-experience` propose, `prompt-auditor` statue, `PromptManager` applique.

L'avis scelle le **sha256 du texte** : toute retouche postérieure invalide l'avis et la
variante redevient inutilisable jusqu'à réexamen. C'est ce qui interdit le contournement par
édition après validation.

```
optimiser-prompt-experience → variante candidate + famille + _provenance
                            → prompt-auditor (indépendant, lecture seule)
                            → _neutralite: {verdict, regle, le, sha256_du_texte}
                            → PromptManager accepte | refuse
```

**Règles communes aux deux familles**

- **C1 — Aucune règle figée.** Aucun énoncé associant un seuil chiffré (distance, durée, âge,
  revenu, température, **multiplicateur**) à un mode ou à un rang d'option. **La frontière passe
  par le nombre, et seulement par lui** (arbitrage du 2026-09-10, cf. §10 Q5) : une conditionnelle
  prescriptive non chiffrée est conforme. C1 n'interdit pas d'orienter vers un mode — en famille
  experte c'est l'objet du prompt (E1) — elle interdit de remplacer le jugement du modèle par un
  seuil mécanique.
  *Rejeté :* « pour les trajets inférieurs à 500 mètres, la marche par défaut », « la marche en
  option de premier ordre pour les segments ≤ 1 km ».
- **C2 — Aucune formule mathématique.** Pas de fonction d'utilité, de coefficient de
  pondération, de ratio ou d'indice calculé.
- **C3 — Aucune valeur de la cible.** Aucune part modale, aucun chiffre CEREMA, aucun nom de
  métrique (L1, EMD, JSD), aucune allusion à un objectif de calibration.
- **C4 — Aucune donnée inconnue de l'agent simulé** à l'instant de la décision.
- **C5 — Lignée tracée.** `derive_de` obligatoire et pointant une variante existante ; diff
  textuel joint ; **changement de famille signalé explicitement** (cas `expert_gem_3.8_v1`,
  déclaré expert et dérivé d'une minimale).
- **C6 — L'auditeur ne réécrit pas.** Il rend un verdict, la règle violée et le passage cité.
  Proposer une reformulation le rendrait juge et partie.

**Règles propres à la famille minimale** — s'ajoutent aux communes

- **M1 — Aucun mode nommé, sous aucune forme.** Ni prescription, ni valorisation, ni
  dévalorisation, ni présupposition de rang, ni exemple, ni mention de risque, de coût ou de
  confort attaché à un mode identifié.
  *Rejeté :* « pourquoi la marche n'obtient pas la plus forte probabilité ».
  *Accepté :* « Justifie la répartition en une phrase concise. »
- **M2 — Aucun attribut modal implicite.** Aucun terme qui ne s'applique qu'à un mode sans le
  nommer (« l'effort physique », « l'attente à l'arrêt », « le stationnement »).
- **M3 — Test de permutation.** Permuter les noms de modes dans le texte doit le laisser
  intact. S'il devient absurde, il est directionnel.
- **M4 — Budget de brièveté.** Une variante minimale qui dépasse nettement la tâche et le
  format de sortie n'est plus minimale : soit elle est reclassée experte, soit elle est
  élaguée. Repère indicatif : `b_min` = 22 mots, `minimal_persona` = 97.

**Règle propre à la famille experte**

- **E1 — Le cadrage modal est licite, la règle ne l'est pas.** Nommer un mode, le valoriser ou
  le dévaloriser, décrire ses frictions : conforme. Ce qui bascule en non-conforme, c'est C1 et
  C2. Frontière opérationnelle : *« si tel indicateur franchit tel seuil, alors tel mode »* est
  une règle ; *« l'attente à un arrêt non abrité pèse autant que la marche »* est un cadrage.

### 4.3 Verdicts

`conforme` → utilisable. `conforme_avec_reserve` → utilisable, WARNING au lancement nommant la
règle et le passage. `non_conforme` → `PromptManager` refuse.

### 4.4 Rattrapage

Les 24 variantes passent la grille. Le §1.2 en est la pré-instruction, pas le verdict : les
trois violations y sont déjà identifiées, les deux points de Q1 sont soumis à l'auteur avant
que l'auditeur ne fixe sa jurisprudence.

---

## 5. Archivage des expériences obsolètes (point 5)

**Aucune suppression.** Même mécanique qu'au §3.2, valeur `statut: "archivee"`.

| Catégorie | Expériences | Proposition |
|---|---|---|
| **Définies, jamais exécutées** (0 octet) | `exp_gemini-35-fl_minper_jtir_t0_nosim`, `exp_google-g-4-e_minper_…p2`, `exp_meta-mg_minper_…p2`, `exp_mistral-7b-v_…p2`, `exp_mistral-n-24_…p2`, `exp_mistral-s-32_…p2`, `exp_qwen3-v-32b_…p2`, `exp_qwen3-v-8b-m_…p2`, `exp_qwen36-27b_…`, `exp_qwen38-27b-l_…p2` (10) | `archivee` — définitions conservées, hors listing par défaut |
| **Exécutions avortées** (0 décision) | `exp_gemini-35-fl_expcham5_jtir_t0_nosim`, `exp_gemma-4-31b_minper` | `archivee` |
| **Partielles abandonnées** | `exp_agy-claude-o-46` (8), `exp_meta-mg…_2` (10), `exp_meta-mg…p1` (55), `exp_qwen38-27b_minper` (244) | `archivee` ✅ — toutes sous gabarit invalidé, aucune n'a publié de score. `exp_gemini-35-fl_expcham7` a été **reprise et terminée** le 2026-09-10 (2 639/2 645, composite 10,20) : elle reste `actif`, et mène le classement des décideurs LLM |
| **Doublons de nommage** | `exp_gemini-35-fl_minper` (vide) vs `…_2` (complète) ; `exp_gemini-35-fl_expcham5` (vide) vs `…_2` | archiver la vide, garder le `_2`. **Ne pas renommer** : N12, le nom écrit fait foi |
| **Témoins — jamais archivés** | `exp_alea_nosim`, `exp_majvoiture_nosim`, `exp_durmin_nosim`, `exp_lgbm_jtir_nosim` | `actif` |

Le dossier `echanges/` d'antigravity pèse **44 Mo sur 194**. Hors scellement, il fait doublon
avec `presente` dans `decisions.jsonl`, mais c'est la seule preuve du câblage de l'agent :
**conservé** (Q2 de la spec antigravity, tranchée ici dans ce sens).

---

## 6. Filtrage des modèles inaptes (point 6)

Référence mesurée : **prompt médian 4 642 car. ≈ 1 289 tokens** en entrée, ~400 en sortie, soit
**~1 700 tokens par sollicitation** et **~2 285 sollicitations** par run (≈ 3,9 M tokens).

| Instance | Modèle | Verrou | Verdict |
|---|---|---|---|
| `google_gemini_3_{flash-preview,5,6,7,8}_flash_key1` (5) | gemini-3.x-flash | **`rpd_limit: 20`** → 115 jours/run | **inapte** à pleine masse — raison d'être du canal antigravity |
| `groq_openai_120_key1`, `groq_qwen_qwen3_{6,8}_27b_key1` (3) | gpt-oss-120b, qwen3.x-27b | `tpm 8 000` → ~4,7 req/min malgré `rpm 30` ; **OTPM 1 000 non modélisé** (mesuré le 2026-09-08) | **inapte** — à sortir explicitement de la rotation, pas seulement par `weight` |
| `google_gemma4{2,3}_key1` | gemma-4-26b / 31b | `tpm 16 000` → ~9 req/min → ~4 h/run | apte, lent |
| `cerebras_*` (2) | gpt-oss-120b, gemma-4-31b | `rpm 5`, `tpm 30 000` → ~8 h/run | apte, lent |
| `google_gemini3{1,5}_key{1,2}` (4) | flash-lite | `rpd 500`/clé | apte — **incohérence à vérifier** : un run a passé 2 048 sollicitations en 35 min, au-dessus du RPD configuré |
| `mistral_key1` | mistral-small-latest | `rpm 60` déclaré, **1 000 mesuré** | apte, sous-déclaré |
| `lmstudio_*` (8) | locaux | pas de quota ; `weight: 0.0` depuis le 2026-09-08 | apte hors rotation |

**Critère d'aptitude à formaliser**, appliqué par `experience-estimer` **en refus** :
`rpd_limit ≥ sollicitations_estimées` **et** `tpm_limit ≥ 1 700 × rpm_cible` **et**
`max_tokens_per_request ≥ tokens_prompt + max_tokens`.

*Note batching* : `max_tokens_per_request` vaut 6 000 (LM Studio) et 8 000 (Groq). À 1 289
tokens par persona, un lot de 5 dépasse déjà. Sans effet tant que `unite_sollicitation =
deplacement` ; verrou dur si le regroupement inter-personnes revient.

---

## 7. Modèles ajoutables (point 7)

**LM Studio répond, 12 modèles chargés.**

⚠ **`lmstudio_qwen3_8_27b_key1` servait un autre modèle** ✅ corrigé le 2026-09-10. Il déclarait
`default_model: qwen3.8-27b-local`, un alias qui n'existe pas côté serveur. Vérifié en direct :
LM Studio **ne renvoie pas d'erreur** sur un identifiant inconnu — il répond `HTTP 200` et sert
un autre modèle chargé, en l'occurrence `qwen3-vl-8b-instruct-mlx`, un 8 B de vision au lieu du
27 B demandé. Une mesure produite par cette instance aurait porté un nom de modèle faux sans
que rien ne le signale.

Deux corrections en découlent :

1. `default_model: qwen/qwen3.8-27b`, l'identifiant exact exposé par le serveur.
2. **Garde-fou dans l'adaptateur** : `openai_compatible` compare le champ `model` de la réponse
   au modèle demandé et refuse la substitution (`ProviderClientError` 502 nommant les deux
   modèles et le champ à corriger). C'est l'équivalent, côté serveurs OpenAI-compatibles, du
   refus de substitution que `allowed_providers` assure ailleurs (`llm_agent.py:711`). Une
   réponse sans champ `model` passe : refuser sur un champ absent bloquerait des fournisseurs
   conformes.

**Rectification** : la v2 de ce plan attribuait à ce défaut l'arrêt d'`exp_qwen38-27b_minper` à
244 décisions. C'est faux — la trace de ce run nomme `groq_qwen_qwen3_8_27b_key1` et ses erreurs
disent `passerelle_occupee: Timeout expiré`. Sa cause est la saturation Groq, pas LM Studio. Les
deux problèmes sont réels, ils ne sont pas le même.

| Chargé, non déclaré | Apte ? |
|---|---|
| `qwen/qwen3.8-27b` | oui — déjà voulu, mal nommé (ci-dessus) |
| `minicpm-v-4_5@q4_k_m` / `@q4_k_s` | 4 B vision quantifié — déclarable en témoin bas de gamme, sortie JSON à éprouver d'abord |
| `olmocr-2-7b-1025` | non — OCR |
| `text-embedding-nomic-embed-text-v1.5` | non — embeddings |

Les paliers `gemini-3-flash-preview`, `3.6`, `3.7` sont configurés mais jamais employés
(`weight 0`, `rpd 20`) : exploitables **soit** par un canal type antigravity, **soit** sur
sous-échantillon apparié (20 décisions/jour sur un jeu gelé — 10 jours pour 200 décisions, ce
qui reste honnête si le jeu est fixé d'avance).

**Procédure d'admission** avant toute mise en rotation : 20 cas d'un jeu gelé, conformité au
schéma (somme = 100, index complets), latence, coût quota. Un modèle qui échoue au schéma sur
20 cas n'entre pas.

---

## 8. Plateforme de pilotage (point 8)

### Retenues

**P5 — Statut d'expérience de premier ordre.** `statut.json` (§3.2, §5) + filtre au tableau de
bord. Prérequis des points 3 et 5 : **à livrer en premier**.

**P3 — Refus a priori des expériences infaisables.** `experience-estimer` chiffre déjà quota et
jetons ; il doit **refuser** avec le critère du §6, en nommant le verrou. Coût quasi nul,
évitait les huit runs avortés du §5.

**P1 — File d'attente ordonnancée par quota, avec tri manuel.** `experience-file` et
`experience-ordonnancer` existent. Ajouts : l'ordonnanceur connaît la fenêtre de renouvellement
de chaque fournisseur (`quota_reset_tz` est déjà dans `providers.yaml`, seul Google le porte) ;
un run qui bute sur `rpd` passe en `en_attente_quota` et **reprend seul** au reset.
**L'ordre proposé reste modifiable à la main** (`experience-ordonnancer` conserve la main sur
la position ; l'automatisme propose, il n'impose pas) — exigence de l'auteur.

**P2 — Lancement à heure fixe.** `planifie_a: '09:05 America/Los_Angeles'` par expérience,
appelant `experience-lancer`. **Adossé à P1**, jamais un cron indépendant : deux mécanismes
lançant des runs sur le même quota, c'est la panne assurée.

**P4 — Registre de santé des fournisseurs.** Les limites de `providers.yaml` sont déclaratives
et fausses en plusieurs points (Mistral sous-déclaré ×16, OTPM Groq absent, RPD Google
incohérent avec un run observé). Sonde quotidienne mesurant les limites réelles (en-têtes
`x-ratelimit`, Cloud Quotas API) et signalant l'écart avec le fichier.

**P8 — Conservation de la sortie littérale du modèle.** `reponse_brute` du canal antigravity
est une re-sérialisation (2 287 réponses en JSON nu, deux formes selon le segment) : aucune
pièce de l'archive ne montre ce que le modèle a émis. Champ `sortie_litterale` distinct, jamais
reformaté.

**P6 — Verrou de comparabilité** (retenue le 2026-09-10). `make comparer` refuse déjà d'apparier deux exécutions dont
les empreintes partagées diffèrent. La proposition : **étendre ce refus au statut** — refuser
de comparer une expérience `invalide` ou `archivee` à une expérience `active` sans un
`--inclure-invalides` explicite. Autrement dit, une fois `minimal_persona` invalidé, un
`make comparer` entre le run gemini-3.8-flash et un run `expert_chaine` s'arrêterait en
disant « A est invalidée le 2026-09-10 (règle M1) » au lieu de sortir un tableau d'écarts qu'on
pourrait citer sans savoir. Garde-fou d'usage, pas contrainte de calcul : les données restent
lisibles, seul le rapprochement automatique est freiné.

### Rejetée

~~P7 — Vue « lignée de prompt »~~ et ~~§2.4 — correctifs de template~~ — écartés par l'auteur.

---

## 9. Ordre de livraison proposé

**Fait le 2026-09-10** — §4.1 déclaration des familles et `PromptManager.famille` · §2.2 blocs
`_invalidation` sur les trois variantes · §2.3 création de `prompt_minimal` · **§2.1 refus de
service** (`VariantePromptInvalide`, échec au démarrage si le prompt actif est invalidé,
empreintes toujours calculables) · 9 tests de non-régression · documentation et changelog.

**Fait aussi le 2026-09-10** — **P5 + §3.2** statut d'expérience livré · **§3.1 + §5** statuts
appliqués (4 invalidées, 16 archivées, 10 actives ; 204 Mo intacts, 20 exécutions et 14
`scores.json` toujours sur le disque).

**Fait aussi le 2026-09-10, second lot** — **P6** verrou de comparabilité
(`ComparaisonRefusee`, `--inclure-invalides`, motif rappelé au-dessus des écarts, 4 tests) ·
**§6 + P3** module `experiences/aptitude.py`, refus a priori dans `experience-estimer` et
`experience-lancer`, `--ignorer-aptitude` (12 tests) · **§4.2** agent `prompt-auditor`
(`.claude/agents/`) + application de l'avis `_neutralite` par `PromptManager`, sceau du texte,
mode strict désarmé (8 tests) · **P8** champ `sortie_litterale` verbatim dans le contrat IPC et
la trace, compteur et alarme (4 tests).

**Rejeté par l'auteur** : ~~§2.4 correctifs de template T1/T2/T3~~.

**À faire :**

1. **§7** — correction de `lmstudio_qwen3_8_27b_key1` (une ligne, débloque un modèle) —
   expliquée le 2026-09-10, en attente d'accord.
2. **§4.4** — rattrapage : faire auditer les 25 variantes par `prompt-auditor`, puis armer
   `exiger_avis_neutralite`. Tant que le mode strict est désarmé, un prompt non audité passe
   avec un simple WARNING.
3. **P1, P2, P4** — file ordonnancée par quota (tri manuel conservé), lancement à heure fixe,
   sonde de santé des fournisseurs. Les trois touchent l'orchestrateur vivant ou consomment du
   quota : à traiter en une passe dédiée.

*Hors séquence, à la main de l'auteur* : le rejeu apparié `minimal_persona` vs `prompt_minimal`.

## 10. Questions — tranchées le 2026-09-10

5. **C1 doit-elle mordre sur les conditionnelles prescriptives non chiffrées ?** L'audit du
   2026-09-10 signalait qu'une règle figée se met en conformité avec C1 en dé-quantifiant son
   seuil sans rien perdre de son effet directif. → **Non** (auteur, 2026-09-10). C1 garde le
   nombre pour seul critère. Conséquence assumée : « augmente significativement la durée […]
   privilégie son véhicule disponible » est conforme, et `expert_chaine_m6` reste conforme avec
   sa clause « aucune attraction sur les trajets locaux de proximité ». Raison : orienter vers un
   mode est licite et voulu en famille experte ; ce que C1 proscrit, c'est le seuil qui retire au
   modèle l'appréciation du cas. **Aucun des 18 avis déjà inscrits ne change** — les auditeurs
   avaient déjà traité ces formes comme conformes, l'arbitrage les ratifie.

1. ~~Les deux nombres du §1.3~~ → **cadrages acceptables**. Les runs `expcha*` restent valides.
2. `exp_gemini-35-fl_expcham7` (1 754/2 645) → **reprise**, à une condition : la reprendre
   **avant** les correctifs de template T1/T2, sans quoi l'exécution enjamberait un changement
   de gabarit et ses décisions ne se compareraient plus entre elles. Ni la déclaration de
   famille ni les blocs `_invalidation` ne gênent : ils ne touchent pas au `content`, l'empreinte
   du gabarit `expert_chaine_m7` est inchangée — vérifié.
3. ~~Rejeu apparié~~ → **pris en charge par l'auteur**.
4. ~~P6~~ → **retenue**.
