## [2026-07-24] Calibration : notifications Discord détaillées (« où en est la campagne »)

Les notifications du daemon de calibration disaient **qu'il** travaillait, jamais **où il
en était** : entre « Daemon démarré » et « Quota épuisé », des heures de silence, sans
savoir s'il en était à la dixième ou à la deux-centième coalition Shapley. Le salon
Discord suit désormais la campagne **étape par étape**.

Au **démarrage** de chaque passe, un message « d'où l'on part » : itération de reprise et
cible, meilleur composite connu, prompt courant (score, nombre de mots, blocs mutables),
tailles des jeux train/val/screening, modèle d'éval et nombre de coalitions Shapley
attendues. À l'**arrêt** (quota épuisé ou budget atteint), le message symétrique : l'étape
exactement interrompue, le travail de la passe (itérations, acceptées/rejetées, évals
payées vs servies par le cache, appels LLM, durée) et le gain de composite obtenu.

Entre les deux, les **étapes principales** sont annoncées (éval initiale, proposition de
mutation, gate de strate, screening, paliers de racing, éval complète, attribution
Shapley, validation, compaction), chaque **itération** publie sa mutation puis son verdict
(composite, Δ, cause de rejet), et un **battement de cœur** (toutes les 15 min par défaut)
donne l'avancement *à l'intérieur* d'une étape longue — c'est lui qui répond à « il en est
où, sur ses 250 valeurs de Shapley ? ».

**Avant :** « 🟢 Daemon démarré » … 6 h de silence … « ⏸️ Quota épuisé — reprise demain 07:00 »
**Après :** « ▶️ Passe démarrée — itération 11 → 50, best 36.80 » … « 🔷 Shapley (init) 253
coalitions attendues » … « ⏳ Avancement — Shapley 124/253 (49 %), 87 payées, 37 cache » …
« ⚖️ Itération 12 → accepted, composite 34.20 (Δ=-2.60) » … « ⏸️ Quota épuisé pendant :
attribution Shapley après acceptation #5 · 168/253 (66 %) — 3 itérations, 412 évals payées »

Réglable dans la config du run (`notify_stages`, `notify_iterations`,
`notify_heartbeat_seconds`, `notify_min_interval_seconds`) ; sans webhook Discord, rien ne
change et rien n'est envoyé.

---

## [2026-07-23] Calibration : notifications Discord & digest quotidien

Le daemon de calibration autonome peut désormais **remonter son état sur un salon
Discord**, pour suivre une campagne cloud sans SSH. Un webhook (pas de bot) reçoit
**uniquement les transitions d'état** : démarrage, quota épuisé → mise en veille (avec
l'heure de reprise), reprise après reset, **nouveau meilleur prompt**, fin de campagne.
Deux ajouts qui ciblent des angles morts : une alerte **⚠️ quand un 429 n'est pas
identifié « per day »** (le cooldown retombe alors sur un délai court — signe que le
libellé Gemini a peut-être changé), et une alerte **☠️ « daemon mort »** portée par
systemd (`OnFailure=`), seul moyen de prévenir en cas de crash/OOM où plus aucun message
applicatif ne peut partir.

Nouveau `calibrate digest` (timer systemd quotidien) : un **récapitulatif lisible**
(itération, meilleur composite, évals payées et mutations acceptées sur 24 h, veille en
cours) **reformulé par Mistral** — modèle distinct du quota d'éval Gemini, donc **sans
entamer le budget** de la campagne ; repli sur un texte brut si Mistral est indisponible.

Le tout est **best-effort et opt-in** : sans `DISCORD_WEBHOOK_URL` dans `~/calib.env`,
aucune notification n'est émise (no-op) ; un envoi qui échoue n'interrompt jamais la
campagne (le store SQLite reste la source de vérité). Aucun contenu de prompt ni clé
n'est transmis — seulement des métriques agrégées.

**Before :** campagne cloud silencieuse — il fallait `journalctl -u calib` en SSH pour
savoir si elle avançait, dormait ou était morte.
**After :** l'essentiel arrive sur Discord (veille/reprise/best/fin/échec) + un digest
quotidien ; la supervision SSH devient optionnelle.

---

## [2026-07-23] Calibration : daemon autonome & cooldown quota (24h/reset)

La calibration de prompt peut désormais tourner **entièrement seule sur le cloud** et
exploiter au mieux le quota journalier (RPD/TPD). À l'épuisement du quota, les requêtes
LLM sont **mises en veille jusqu'à la réouverture du quota** — la durée est lue dans le
429 du provider, avec une subtilité : pour un quota **journalier** (marqueur `PerDay`),
le délai renvoyé par Gemini sous-estime le temps réel jusqu'au reset, donc on vise le
**prochain minuit Pacific** (`quota_reset_tz`, DST géré) pour reprendre pile sur le quota
frais. Le cooldown est **persisté dans le store** (portée globale), donc il survit à un
redémarrage.

Nouveau mode `calibrate run --loop` : un **daemon** qui dort pendant le cooldown
(heartbeat `💤` dans les logs) puis reprend seul — plus besoin de cron. Une unité systemd
(`cloud/calib.service`) le maintient en vie (démarrage au boot, redémarrage après crash).
Le lancement cron one-shot reste supporté et bénéficie de la même **garde de démarrage**
(il sort proprement si un cooldown est encore actif au lieu de re-solliciter l'API).

**Avant :** quota épuisé → le run s'arrêtait ; il fallait un cron externe pour rejouer,
et une relance trop tôt re-tapait l'API avant le reset.
**Après :** `run --loop` sous systemd → la campagne consomme le quota du jour, se rendort
jusqu'au reset, reprend, et progresse jusqu'à `max_iterations` sans supervision.
Réglages : `quota_reset_tz`, `cooldown_fallback_seconds`, `cooldown_max_seconds`,
`daemon_sleep_chunk_seconds`.

---

## [2026-07-22] Calibration : arrêt propre à l'épuisement du quota

La boucle de calibration de prompt peut désormais s'arrêter proprement quand le quota
journalier du provider d'éval est épuisé, au lieu de marteler l'API en boucle sur des
coalitions vouées à l'échec. Un coupe-circuit compte les échecs de lot **consécutifs**
(paramètre `eval_max_consecutive_errors`, défaut 3) : tout succès remet le compteur à
zéro, donc une coupure réseau transitoire isolée ne l'arrête pas — seule une salve
franche (quota mort) le fait. À l'arrêt, le cache est intact : relancer le run reprend
exactement à la première coalition non payée.

**Avant :** quota épuisé → le run continuait des heures, chaque coalition rejouant 5
retries × N lots en pure perte, jusqu'au `Ctrl-C` manuel (trace Python en prime).
**Après :** au 3ᵉ échec consécutif, message `🛑 … quota probablement épuisé`, arrêt
propre sans trace, reprise gratuite au run suivant. `eval_max_consecutive_errors: 0`
rétablit l'ancien comportement.

---

## [2026-07-21] Quotas Gemma corrigés : +90 % de budget journalier, TPM enfin borné

Les deux providers Gemma (`google_gemma42` / `google_gemma43`) étaient déclarés avec des quotas
free tier erronés. Relevé sur le dashboard AI Studio, le réel est **RPM 30 · TPM 16 000 · RPD
14 400** par modèle — la config annonçait `rpm 15`, `tpm null` (« illimité ») et `rpd 1500`.

Deux effets concrets :
- **Budget journalier** : chaque Gemma passe de 1 500 à 14 400 requêtes/jour. À eux deux ils offrent
  désormais ~28 800 req/j, de loin le plus gros pourvoyeur free tier (vs 500/j pour gemini-3.1-flash-lite).
- **Anti-saturation** : le TPM était déclaré illimité, donc le load-balancer envoyait de gros batchs
  aux Gemma alors qu'ils plafonnent à 16 000 tokens/min (≈ 5 agents de 3k tokens). Le TPM réel est
  maintenant renseigné : les batchs s'auto-dimensionnent et un `max_tokens_per_request` évite les
  HTTP 413. Le `weight` tombe de 1.0 à 0.36 (les Gemma sont bornés par le TPM, comme Groq).

**Avant :** Gemma bridés à 1 500 req/j et réputés à TPM illimité → budget gâché + risque de saturation.
**Après :** Gemma exploités à 14 400 req/j chacun, débit tokens correctement borné.

---

## [2026-07-22] Calibration : poids du composite auditables (sensibilité, zéro LLM)

Les poids du composite étaient posés à la main (`global 1.0, âge 0.5, genre 0.3…`) et
mélangeaient l'**échelle** d'un terme (une L1 sur 15 tranches d'âge et une JSD n'ont pas
la même magnitude) et son **importance**. Deux ajouts, sans aucun appel modèle :

- Les losses acceptent désormais des **poids par instance** (`weights=`) ; le composite
  reste linéaire (Shapley/backtest inchangés).
- Nouvelle commande **`calibrate weights`** : reclasse les prompts déjà évalués sous
  plusieurs schémas de pondération — `uniform`, `informativity` (dérivés du pouvoir
  discriminant de chaque axe dans EMC²), `scaled` (**normalisation d'échelle** par le
  prompt seed), `strat_x2` / `strat_half` — et dit si le **meilleur prompt reste le
  meilleur** (stabilité + corrélation de rang). Répond de façon chiffrée à « pourquoi
  0.3 pour le genre ? ».

**Avant :** impossible de savoir si le classement des prompts tenait aux poids choisis.
**Après :** `calibrate weights` le vérifie en une commande, sur les décisions déjà
stockées (zéro token). *(Sur la campagne actuelle : classement STABLE, corrélations de
rang 0.96–1.0 — le gagnant ne dépend pas de la pondération.)*

---

## [2026-07-21] Calibration : mise en page du message de mutation resserrée

Le message envoyé au modèle de mutation est réordonné pour coller à sa lecture naturelle :
- La **Mémoire des leçons** passe **après** l'« Historique des mutations » (en-tête renommé
  « Historique des mutations et enseignements »), dont elle est le prolongement — au lieu d'être
  intercalée avant.
- Le rappel `💡 Opérateur à privilégier ce tour` **clôt** désormais le message (juste après la
  consigne JSON), au lieu d'être noyé entre le prompt complet et l'instruction.
- La section « ⚖️ Diversité des cibles » est **supprimée** : le garde-fou anti-resoumission
  (tabu + prescreen) empêche déjà de re-toucher trivialement le même bloc, la consigne faisait
  doublon.

**Avant :** leçons avant l'historique, rappel d'opérateur au milieu du message, section diversité
en plus.
**Après :** historique → enseignements, prompt complet, instruction, puis opérateur suggéré en
dernière ligne ; message plus court et plus lisible.

---

## [2026-07-21] Calibration : liste des opérateurs et coût-mot rappelés dans la consigne de mutation

La consigne finale envoyée au modèle de mutation (`build_mutation_user_msg`) rappelle désormais
explicitement, juste avant le JSON attendu : (1) les **7 actions possibles** (`modify`, `delete`,
`insert`, `condense`, `reorder`, `merge_blocks`, `split`) avec un résumé d'une ligne chacune ;
(2) le **coût de longueur** — chaque mot du prompt ajoute 0.05 pt d'écart (`length_penalty`), donc
à effet égal la formulation la plus courte est préférée. Vaut pour les deux chemins (candidat
unique et multi-candidats).

**Avant :** la palette d'opérateurs n'apparaissait que dans le prompt système ; la consigne finale
ne mentionnait que « modify » (l'exemple de JSON), et l'incitation à la concision n'était pas rappelée
au moment de proposer.
**Après :** le mutateur voit la liste complète des actions et le coût-mot à l'endroit où il rédige sa
proposition — il exploite mieux `condense`/`delete`/`merge_blocks` et raccourcit à effet égal.

---

## [2026-07-21] Calibration : `emd_jsd` devient la loss par défaut

La métrique par défaut d'une campagne de calibration est désormais `emd_jsd` (EMD ordinal
sur âge/distance + JSD nominal sur global/occupation/genre/motif + pondération continue par
effectif), y compris quand aucun `loss` n'est précisé. Tous les fichiers de config
l'utilisaient déjà ; seul le défaut codé dans `RunConfig` restait sur l'ancienne `l1_composite`.

**Avant :** une campagne lancée sans `loss` explicite tombait sur `l1_composite` (toutes les
catégories traitées comme interchangeables — un glissement d'âge adjacent coûtait autant qu'un
glissement lointain).
**Après :** défaut `emd_jsd`, qui respecte l'ordre des dimensions ordinales. `l1_composite`
reste sélectionnable et recalculable rétroactivement en backtest.

---

## [2026-07-21] Calibration : contexte du mutateur refondu (« ingénieur prompt »)

Le message envoyé au modèle de mutation (calibration du prompt) a été réécrit pour aller à
l'essentiel, parler d'**écart** (et non de « score composite »), et présenter le prompt de
façon plus lisible :

- **Phrase d'intro** : le message s'ouvre sur la mission (« Tu es ingénieur prompt : ta mission
  est d'optimiser le prompt système ci-dessous… »).
- En-tête `Distribution LLM actuelle :` **sans** le compte de décisions.
- **Hard negatives supprimés** (exemples individuels persona → mode) et bloc **« DEUX leviers
  prioritaires » supprimé** : redondants avec les « pires écarts strate × mode », désormais en
  **top 10** (au lieu de 6) et **sans** l'effectif `n=`.
- Ligne `Score composite actuel` retirée ; partout on parle d'**écart**. L'historique affiche
  `écart total=… (par dimension : global …, âge …, occupation …, …)`, **en toutes lettres**.
- **Historique** borné aux **5 dernières** tentatives.
- **Mémoire de leçons** : jusqu'aux **5 dernières** synthèses de rejet (au lieu d'une seule),
  numérotées.
- **Présentation unifiée du prompt** : chaque bloc est donné **dans l'ordre**, avec son **contenu
  entier** et sa contribution (Δ écart, dimensions aidées/dégradées, effet sur les modes) **sans
  abréviations**, **blocs fixes inclus**. Cette vue remplace l'ancienne table + le dump séparé des
  blocs modifiables.
- Le rappel d'opérateur ne suggère « garde de la diversité » qu'en **multi-candidats**.

**Before :** contexte long et abrégé (compte de décisions, deux leviers, hard negatives, score
composite, table markdown + dump des blocs, abréviations `g/ag/oc`, `voit`, une seule leçon).
**After :** contexte focalisé et lisible (top 10 sans effectif, 5 tentatives, 5 leçons, prompt
présenté bloc par bloc en toutes lettres avec sa contribution), plus clair pour le mutateur.

---

## [2026-07-21] Sources réorganisées en trois dépôts git + calibration en dépôt autonome

Le code est désormais réparti en **trois dépôts git** aux responsabilités claires :

- **`llm-agents-gama`** — le projet principal (pipeline LLM, GAMA, docker, docs).
- **`prompt_calibration`** — l'outil de calibration de prompt, extrait dans son propre
  dépôt (`github.com/Ytlse/prompt_calibration`), cloné à la racine sous
  `prompt_calibration/` (auparavant `scripts/prompt_calibration/`).
- **`eqasim-llm-toulouse`** — la génération de population eqasim (`eqasim-toulouse/`).

Les deux derniers sont imbriqués à la racine du projet mais **ignorés** par le dépôt
principal (comme `eqasim-toulouse/` l'était déjà). Tous les liens vers l'ancien chemin
`scripts/prompt_calibration/` ont été réparés : montage Docker, endpoint `/calibrate`,
skill `prompt_calib_context`, doc d'architecture, scripts de déploiement cloud, et le
`Makefile`/configs internes du dépôt de calibration (venv, jeux gelés, ressources
partagées). La suite de tests de calibration (209 tests) repasse au vert.

**Before :** la calibration vivait dans `scripts/prompt_calibration/` ; après son
déplacement, le lancement depuis l'IHM GAMA (`POST /calibrate`) et `make test` étaient
cassés (chemins morts, venv introuvable, imports périmés).
**After :** `prompt_calibration/` est un dépôt autonome monté dans le conteneur
`controller` sous `/app/prompt_calibration` ; `/calibrate` et `make test` fonctionnent.

---

## [2026-07-20] Calibration : Shapley 6× moins cher (jeu screen restauré) + console lisible

Trois corrections issues du diagnostic d'une campagne réelle :

- **Jeu `screen` ajouté aux jeux gelés v1** : gelés avant la phase 4, ils n'avaient
  pas le sous-échantillon de screening — Shapley et le screening se repliaient **en
  silence** sur le train complet (99 lots ≈ 100 requêtes par coalition). Le jeu
  (83 personas, filtre déterministe `in_screen` sur le train gelé — identique à ce
  que le générateur aurait produit) ramène chaque coalition à ~17 lots : **~6× moins
  de requêtes**, ~25-30 coalitions/jour sous quota gratuit au lieu de ~5.
- **Alarme sur le repli** : si le jeu `screen` manque, le lancement affiche désormais
  `[ALARME]` avec le surcoût et le remède, au lieu de dégrader silencieusement.
- **Console désambiguïsée** : le libellé Shapley porte le hash de la coalition
  (`shapley[2b:0640c803]`) — deux coalitions de même taille ne se confondent plus ;
  chaque coalition déjà payée affiche `✓ cache : …` à la reprise, et chaque passe se
  conclut par un bilan `N payée(s), M servie(s) par le cache`.

**Avant :** à la reprise, impossible de distinguer un recalcul payant d'un cache hit ;
Shapley consommait ~100 requêtes par coalition sans signal.
**Après :** la console montre ce qui est resservi gratuitement, et Shapley tourne sur
le jeu de screening prévu par l'architecture.

---

## [2026-07-20] Calibration : Shapley cumulatif à graine fixe — mêmes tokens, plus de précision

Le recalcul Shapley après chaque mutation acceptée re-tirait des permutations
aléatoires neuves : la plupart des coalitions évaluées ne retombaient jamais sur le
cache, et chaque passe repayait des évaluations qui n'apportaient pas d'information
nouvelle. Nouveau régime **cumulatif** (activé dans les configs de campagne) :

- **Socle à graine fixe** : les mêmes permutations sont rejouées à chaque passe.
  Après une réécriture de bloc, toutes les coalitions sans ce bloc sont servies par
  le cache (zéro appel LLM) — on ne paie que ce qui contient du contenu nouveau.
- **Addon plafonné** : quelques permutations fraîches s'ajoutent à chaque mutation
  acceptée (`shapley_addon_per_accept`, plafond `shapley_max_permutations`) — la
  précision de l'attribution de crédit augmente au fil de la campagne, au moment où
  les décisions (compaction, publication) en dépendent le plus.
- **Plafond ajustable en cours de campagne** : modifier le YAML suffit, pris en
  compte à la reprise suivante sans invalider le moindre calcul déjà payé.

**Avant :** chaque recalcul Shapley repayait ~toutes ses coalitions ; précision constante.
**Après :** un recalcul après réécriture ne paie que les coalitions touchant le bloc
modifié ; la précision croît (25 → 50 permutations) pour un coût par passe borné.

L'ancien comportement reste disponible (`shapley_addon_per_accept: 0`).

---

## [2026-07-17] Calibration : lancement sur une VM Google gratuite (guide clé en main)

La campagne de calibration de prompt peut désormais tourner **toute seule sur une machine
Google Cloud gratuite** (offre « Always Free » `e2-micro`), sans quitter le poste des yeux.
Un dossier `scripts/prompt_calibration/cloud/` fournit tout le nécessaire :

- **`README_CLOUD.md`** — un guide pas à pas « pour les nuls » (création de la VM, upload
  des données, clé API, automatisation), pensé pour quelqu'un qui n'a jamais touché à
  Google Cloud.
- **`config/cloud.yaml`** — la configuration de campagne côté cloud (chemins relatifs du
  dépôt, quota free tier Gemini).
- **`setup_vm.sh`** / **`run_daily.sh`** — installation en une commande, puis un réveil
  `cron` quotidien qui reprend la campagne là où le quota du jour l'avait arrêtée.
- **`data_to_upload.tar.gz`** — les jeux gelés `v1` (hors Git) prêts à envoyer à la VM.

**Coût : 0 €.** La campagne s'étale sur plusieurs jours (500 requêtes Gemini/jour en
gratuit), mais la reprise du store SQLite fait qu'il n'y a rien à surveiller : elle avance
un peu chaque nuit jusqu'à la fin.

**Avant :** la calibration ne se lançait qu'en local (poste de dev) ou via l'IHM GAMA.
**Après :** un déploiement cloud gratuit, autonome et reprenable, documenté de bout en bout.

---

## [2026-07-17] Calibration : le mutateur voit du concret (matrice bloc × mode, exemples réels, snippets entiers)

Le mutateur de prompt ne raisonnait que sur des agrégats (distributions, écarts,
contributions par dimension). Trois évolutions lui donnent du concret — **sans aucun
appel LLM supplémentaire** (données déjà persistées, uniquement calcul et formatage) :

- **Matrice bloc × mode** : la table de contribution gagne une colonne « modes poussés »
  (ex. `vélo+4 voit-3`) — l'effet de la présence de chaque bloc sur les parts modales,
  décomposé par Shapley sur les mêmes évals. Le mutateur sait *quel mode* un bloc favorise
  ou freine, au lieu de deviner la corrélation depuis les dimensions.
- **Exemples réels de décisions à corriger** (hard negatives) : jusqu'à 4 décisions
  individuelles du prompt courant (persona → mode choisi) issues des pires strates
  sur-représentées, ex. `Femme, 30 ans, actif, travail, 1-2km → voiture (+70 pts vs cible)`.
  Réglable via `hard_negatives_k` (0 → désactivé).
- **Bibliothèque d'arguments fournie en entier** : les snippets n'étaient montrés que sur
  110 caractères — tronqués en plein argument, le mutateur devait halluciner la fin.
  Contenu complet désormais (cap de sécurité à 300).

**Avant :** le mutateur devinait la relation bloc → mode et n'avait jamais vu une erreur concrète.
**Après :** chaque tour montre qui pousse quoi, et à quoi ressemble une décision aberrante type.

---

## [2026-07-17] Calibration : attribution Shapley globale à chaque acceptation (fin du leave-one-out)

La contribution de chaque bloc au score est désormais **recalculée par attribution de
crédit Shapley après *chaque* mutation acceptée** (et à l'initialisation), sur le jeu de
screening. L'ancienne ablation *leave-one-out* (retrait d'un bloc à la fois) est
entièrement supprimée : elle supposait les blocs indépendants et se trompait sur les
blocs **redondants** (jugés inutiles à tort) et **synergiques** (crédit compté deux
fois). Shapley répartit exactement le gain entre les blocs, ces deux cas compris.

**Avant :** ablation locale rapide (leave-one-out) du seul bloc touché après chaque
acceptation, et recalcul Shapley global seulement toutes les 5 acceptations — la carte
de contribution montrée au mutateur pouvait être partiellement périmée entre deux
recalculs globaux.
**Après :** carte de contribution Shapley **complète et à jour à chaque acceptation**.
Le coût reste maîtrisé : le cache adressé par contenu du store rend gratuites les
coalitions déjà évaluées (entre permutations, entre acceptations, entre runs).

Options de configuration retirées : `shapley_enabled`, `shapley_every`,
`global_ablation_every` (le comportement est désormais unique). `shapley_permutations`
(=25) et `shapley_truncation_tol` (=0.5) restent réglables.

---

## [2026-07-17] Calibration : le mutateur apprend de ses rejets (mémoire de leçons)

Le mutateur de prompt **synthétise désormais les raisons récurrentes de ses rejets**
avant de proposer, et cette synthèse est mémorisée puis réinjectée au tour suivant.
Objectif : rompre la boucle où le mutateur re-cible sans fin le même bloc parce que le
contexte affiché ne bougeait pas entre deux rejets.

Chaque rejet de l'historique est aussi **étiqueté par catégorie** : `[fond]` (une vraie
leçon existe — ne pas y retourner) vs `[bruit]`/`[seuil]`/`[doublon]` (l'idée n'est pas
invalidée, juste non significative — la reformuler). Ce garde-fou évite que le mutateur
abandonne à tort une piste correcte rejetée pour simple non-significativité statistique.

**Avant :** les causes brutes (`Δ=+0.30@n=25`, `motif +12`) étaient affichées mais jamais
généralisées ni distinguées ; le mutateur re-proposait souvent des variantes déjà écartées.
**Après :** une mémoire de leçons roulante (bornée, persistée, reprise gratuite) guide chaque
proposition vers un changement réellement distinct, en tenant compte de la nature du rejet.

La synthèse est produite dans le même appel que la proposition (coût quasi nul, aucun appel
LLM supplémentaire). Réglable via `reflection_enabled` / `lessons_max_chars` (désactivable
pour comparaison A/B).

**Garde-fou dur associé** : « ne resoumets jamais le même texte ni une variante triviale »
n'est plus qu'une consigne — c'est appliqué en code **quelle que soit la config**. Une
proposition sans changement réel, ou quasi identique à un rejet récent, est écartée **sans
aucune éval** (dans le chemin single-candidat par défaut comme dans l'entonnoir). Une
ré-soumission triviale redevient permise une fois le contexte changé (tenure du tabu).

---

## [2026-07-17] Calibration : évaluation des itinéraires sur Gemini

La campagne de calibration (`run.yaml`) évalue désormais les itinéraires avec
**Gemini** (`google_gemini31` / `gemini-3.1-flash-lite-preview`) au lieu de Mistral.
Le prompt calibré sera donc spécifique à Gemini — le modèle réellement servi en
production pour la décision d'itinéraire.

**Avant :** éval sur `mistral-small-latest`, mutations sur Gemini.
**Après :** éval **et** mutations sur Gemini `gemini-3.1-flash-lite-preview`.

⚠ Éval et mutation partagent maintenant le même quota provider Gemini. Si ce quota
devient contraignant, basculer `mutation_model` sur un autre modèle (ex.
`google_gemma42`) rétablit la séparation.

> Reprendre une campagne existante depuis un store calibré sur Mistral n'est pas
> valide (le cache d'éval Mistral ne s'applique pas à Gemini) : repartir d'un store
> neuf. `run2.yaml` reste volontairement sur Mistral pour comparaison.

---

## [2026-07-17] Calibration : retour à un essai unique avec paliers 25/50/75 %

La calibration de prompt (`scripts/prompt_calibration/`) évalue de nouveau **un seul
essai par itération** au lieu de quatre candidats en parallèle. Cet unique essai passe
par des **paliers progressifs à 25 %, 50 % puis 75 %** du jeu d'entraînement : dès qu'un
palier **n'améliore pas** le composite du prompt courant sur le même sous-échantillon,
l'essai est **abandonné immédiatement** (verdict `rejected_race`), sans jamais payer
l'évaluation complète ni les paliers suivants.

**Avant :** 4 candidats proposés par appel de mutation, départagés par racing/screening,
le meilleur passant l'éval complète.
**Après :** 1 candidat, filtré par arrêt précoce à 25/50/75 % — moins d'appels LLM
gaspillés sur des essais non prometteurs, trajectoire plus simple à suivre.

Nouveaux défauts : `n_candidates: 1`, `racing_enabled: true`,
`racing_rungs: [0.25, 0.50, 0.75]`. Le racing multi-candidats (gate de strate +
successive halving) reste disponible en remontant `n_candidates`.

---

## [2026-07-16] Calibration : racing ciblé par strate (successive halving)

Nouvelle stratégie de sélection des candidats dans l'entonnoir de
`scripts/prompt_calibration/`, **désactivée par défaut** (`racing_enabled: false`).
Elle remplace le *screening one-shot* — une seule mesure bruitée, jugée sur le
composite global — par un **racing multi-tours** précédé d'un **gate de strate**.

- **Gate strate.** Une itération sur `racing_target_every`, les candidats sont d'abord
  évalués **uniquement** sur la strate la plus mal représentée (ex. `genre[femme]`) ;
  ceux qui n'améliorent pas son écart sont éliminés d'emblée (`rejected_gate`). Si la
  strate est trop petite ou si le gate vide la liste, **repli global** — l'itération
  n'est jamais bloquée.
- **Successive halving.** Les survivants passent des paliers de train **croissants**
  (`racing_rungs`, ex. 15 % → 35 % → 70 % → 100 %) ; à chaque palier on ne garde que la
  meilleure moitié. Le budget d'éval se concentre sur les candidats qui tiennent.
- **Garde-fou statistique.** On ne départage jamais deux candidats trop proches
  (`racing_min_gap`) ou dont l'IC bootstrap chevauche — évite d'éliminer par malchance
  un candidat qui aurait gagné sur le train complet (`rejected_race` sinon).
- **Cache respecté.** Chaque palier passe par le store content-addressed ; seule la
  fraction complète réutilise le label `train`, donc l'éval complète du gagnant est
  servie par le cache quand la boucle la refait — le racing ne « repaie » pas l'historique.

**Avant :** un seul tirage de screening (~20 % du train) sur le composite global
désigne le gagnant ; les strates en échec ne sont jamais ciblées.
**Après (opt-in) :** budget concentré sur les candidats prometteurs et sur la pire
strate ; verdicts `rejected_gate` / `rejected_race` visibles au dashboard.

---

## [2026-07-16] Calibration : contexte mutateur plus lisible + diversité des blocs ciblés

Quatre améliorations du contexte fourni au mutateur de `scripts/prompt_calibration/`,
suite à une revue du rapport de mutation.

- **Légende unique dans le prompt système.** Les abréviations des dimensions
  (`ag=âge`, `oc=occupation`…) et les **conventions de signe** sont désormais
  définies une seule fois dans le prompt système du mutateur (`LEGEND_AND_SIGNS`),
  au lieu d'apparaître de façon conditionnelle et dispersée dans chaque section.
- **Signes explicités, en termes d'écart.** Le composite est une **perte à
  minimiser** ; un **Δ>0 = bloc utile**. Dans les colonnes, « + » = le bloc
  **rapproche de la cible EMC²** (réduit l'écart), « − » = il **creuse l'écart** —
  même orientation que Δ tot.
- **Table de contribution bloc × dimension, autoportante.** L'« analyse d'ablation »
  en crochets compacts est remplacée par une **table markdown** (`format_contrib_table`) :
  une ligne par bloc, une colonne par dimension (en-têtes explicites « nom (abrév) »,
  ex. `occupation (oc)`), + Δ total, triée par utilité. Une **légende de lecture des
  signes** est imprimée juste au-dessus de la table (dans le message utilisateur, pas
  seulement dans le prompt système) → lisible sans avoir à remonter à la légende
  globale. Le diagnostic textuel n'est conservé que pour les blocs nuisibles (canal mode).
- **Diversité des blocs ciblés.** Le mutateur avait tendance à toujours retoucher le
  même bloc (souvent le premier bullet). Le prompt rappelle maintenant les blocs
  récemment modifiés (`_recent_blocks`) et exige, en multi-candidats, un **bloc-cible
  distinct** par candidat ; l'entonnoir écarte sans éval les doublons de bloc (nouveau
  verdict `rejected_dup_block`), un `insert` restant distinct d'un `modify` du même ancrage.

Tests : 189 verts (`calibration/tests/`). La piste plus ambitieuse (racing ciblé par
strate + successive halving) est spécifiée dans `docs/racing-cible-strate.md`, à
implémenter ultérieurement.

**Avant :** légende parfois absente, signes ambigus, contribution en crochets denses,
mutations concentrées sur un seul bloc.
**Après :** légende + conventions de signe systématiques, table lisible, recherche
répartie sur des blocs variés.

---

## [2026-07-16] Makefile calibration : lancer un essai et l'interface en une commande

`scripts/prompt_calibration/` dispose désormais d'un Makefile. `make run essai3`
lance (ou relance/reprend au point d'arrêt) l'essai 3 dans sa propre branche isolée
du store, et `make ui` ouvre le dashboard Streamlit. Autres raccourcis : `status`,
`export`, `finalize`, `backtest`, `datasets`, `test`. Plusieurs essais peuvent
évoluer en parallèle sans se marcher dessus.

**Avant :** il fallait retenir et taper la ligne complète `../../llm-agents/.venv/bin/python
-m calibration.cli run --config … --branch …`
**Après :** `make run essai3` / `make ui` — la branche et la config (`runN.yaml`,
sinon `run.yaml`) sont résolues automatiquement à partir du nom d'essai

---

## [2026-07-16] Dashboard calibration : filtre d'expérience global et persistant

Le dashboard de calibration gagne un filtre **Expérience** unique dans la barre
latérale (menu de gauche) : on choisit une branche/îlot (ou « Toutes les branches »)
et **toutes les vues** s'y restreignent d'un coup — Timeline, DAG, Distribution,
Comparaison, Pareto, Run et Maintenance. Surtout, la sélection **reste en place quand
on change de page** : plus besoin de refiltrer à chaque vue.

**Avant :** le filtre de branche était local à la vue Timeline et repartait sur
« toutes les branches » à chaque changement de page ; les autres vues n'avaient aucun
filtre d'expérience
**Après :** un filtre unique en barre latérale, appliqué à toutes les vues et
mémorisé d'une page à l'autre

---

## [2026-07-15] Dashboard calibration : vue Comparaison vs vérité terrain + carte d'ablation détaillée

Le dashboard de calibration gagne une vue **Comparaison** : des graphiques en barres
confrontent les parts modales de plusieurs prompts (par défaut le prompt de départ et
le meilleur trouvé) à la **vérité terrain EMC²**, en global ou strate par strate
(âge, occupation, genre, motif, distance — un graphique par catégorie, avec les
effectifs). On voit d'un coup d'œil où un prompt calibré colle à l'enquête et où il
dévie encore, sans aucun réappel LLM (tout est reconstruit des décisions stockées).

La carte d'ablation de la vue DAG affiche désormais le **détail par dimension** de
chaque bloc (une colonne par dimension, dégradé vert/rouge), avec un garde-fou : un
détail incohérent avec le Δ du bloc (évals legacy partielles) est masqué plutôt
qu'affiché faux.

**Avant :** la vue Distribution ne montrait qu'un seul nœud, en global uniquement ;
l'ablation n'affichait qu'un Δ par bloc
**Après :** comparaison multi-prompts vs EMC² par strate ; ablation décomposée par
dimension

Corrige au passage : sélection du nœud seed dans la vue DAG (plantait sur le parent
manquant), et choix de l'éval de référence quand un nœud porte plusieurs évals train
(les artefacts sans décisions brutes sont ignorés).

---

## [2026-07-15] Calibration : impact de chaque bloc détaillé par dimension (âge, motif, …)

La carte d'ablation/Shapley fournie au mutateur ne dit plus seulement qu'un bloc est
utile ou nuisible : elle indique **sur quelles dimensions** il agit, en points de
composite, avec une légende des abréviations. Le mutateur peut ainsi réécrire un bloc
pour conserver sa dimension forte tout en corrigeant son effet secondaire, au lieu de
choisir entre le garder et le supprimer.

Cette décomposition est **gratuite** : le score composite étant une somme pondérée des
dimensions, les mêmes évaluations de coalitions (Shapley) ou d'ablation (LOO) suffisent
— zéro appel LLM supplémentaire. Les contributions sous ±1 pt sont masquées (bruit).

**Avant :** `• bloc_meteo (Δ=+4.2) : Par beau temps, envisage la marche…`
**Après :** `• bloc_meteo (Δ=+4.2) [mo+3 ag+2 | oc-2] : Par beau temps, envisage la marche…`
(légende : g=global, ab=modes absents, ag=âge, oc=occupation, ge=genre, mo=motif,
di=distance, lg=longueur — le bloc aide motif et âge, dégrade légèrement occupation)

Le détail est persisté dans le store (`ablations.scores_json` pour les lignes
`shapley`) et la légende est aussi rappelée dans l'historique des mutations.

**Rétro-compat :** à la reprise d'une campagne lancée avant cette évolution, le
détail est reconstitué automatiquement depuis le store (zéro éval) — le mutateur
voit les crochets dès la première itération reprise. Les prompts de mutation déjà
stockés (vue Timeline) restent figés tels qu'ils ont été générés.

---

## [2026-07-15] Calibration : finalisation et publication du prompt calibré

La calibration de prompt (`scripts/prompt_calibration/`) sait désormais **conclure une
campagne en une commande** : `calibrate finalize` désigne le meilleur prompt trouvé,
mesure sa qualité sur le jeu de test réservé, et le publie.

**Le chiffre publiable.** Le meilleur prompt (toutes branches d'îlots confondues) est
évalué **une seule fois** sur le jeu `test` — un jeu gelé que la boucle d'optimisation
n'a jamais vu, donc une mesure honnête et non surajustée. Le prompt de départ est
évalué sur le même jeu pour donner une comparaison **avant/après** immédiate.

**Le bilan.** La commande imprime, pour le seed et le meilleur : le score par jeu
(entraînement / validation / test) et son évolution, le détail par dimension sur le
test, le nombre de mots du prompt (avant/après), le nombre d'évaluations LLM consommées
et la durée approximative de la campagne.

**La publication.** Par défaut la commande est un **essai à blanc** (rien n'est écrit).
Avec `--write`, le prompt calibré est ajouté à `prompts.yaml` sous une clé horodatée
`calibrated_…` (aucune entrée existante n'est modifiée) ; `--activate` le rend actif.

**Before :** conclure une campagne demandait de retrouver le meilleur prompt à la main,
de l'évaluer et de le recopier dans `prompts.yaml` — sans mesure de test standardisée.
**After :** une seule commande produit le score de test publiable, le bilan avant/après
et l'écriture (optionnelle et explicite) du prompt calibré.

---

## [2026-07-15] Calibration : îlots parallèles, merge et archive de Pareto

La calibration de prompt (`scripts/prompt_calibration/`) peut désormais explorer
**plusieurs pistes en parallèle** plutôt qu'une seule trajectoire, et capitaliser les
arguments qui marchent — ce qui augmente les chances de trouver un meilleur prompt à
budget d'évaluation comparable.

**Îlots parallèles.** `calibrate run --islands 3` fait évoluer 3 branches
indépendantes dans le même historique, chacune avec sa propre boucle reprenable. Elles
avancent à tour de rôle sous le même budget de requêtes ; toutes les quelques
itérations, le meilleur prompt d'un îlot est **proposé** (jamais imposé) à l'îlot
voisin — il n'est adopté que s'il améliore vraiment ce dernier. On évite ainsi qu'une
seule mauvaise piste condamne toute la campagne.

**Merge (crossover).** Deux prompts **complémentaires** — l'un bon sur l'âge, l'autre
sur le motif — peuvent être fusionnés par le modèle de mutation en un prompt enfant qui
combine leurs forces, puis évalué comme n'importe quel candidat (deux bons parents ne
font pas toujours un bon enfant : aucun merge n'est gardé sans mesure).

**Archive de Pareto.** Le score composite écrase six dimensions en un seul chiffre ;
deux prompts au même score peuvent en réalité être forts sur des dimensions
différentes. L'archive conserve désormais tous les prompts **non dominés** (ceux
qu'aucun autre ne bat sur toutes les dimensions à la fois) — matière première des
départs d'îlots diversifiés et des parents de merge. Une nouvelle vue **Pareto** du
dashboard la rend visible (nuage de compromis + bibliothèque d'arguments).

**Bibliothèque d'arguments.** Chaque bloc ajouté ou réécrit qui apporte un gain net est
capitalisé (taggé par le mode qu'il a aidé) et resservi au modèle de mutation comme
matière à réutiliser — les îlots se fertilisent ainsi mutuellement, et une future
campagne peut démarrer avec cette banque.

**Before :** une seule trajectoire d'optimisation ; un prompt au score équivalent mais
au profil complémentaire était perdu ; les bons arguments trouvés n'étaient pas réutilisés.
**After :** plusieurs îlots explorent en parallèle, échangent leurs meilleurs prompts et
peuvent les fusionner ; les compromis non dominés sont archivés et les arguments
gagnants capitalisés.

---

## [2026-07-14] Calibration : attribution de crédit par valeur de Shapley

La calibration de prompt (`scripts/prompt_calibration/`) mesure désormais **plus
justement** ce que chaque bloc du prompt apporte au score, ce qui oriente mieux les
mutations et les suppressions.

**Le problème de l'ancienne mesure.** Jusqu'ici, l'importance d'un bloc était estimée
en le retirant seul et en regardant la variation du score (« ablation un-bloc-à-la-fois »).
Cette mesure se trompe dès que les blocs interagissent : deux blocs qui disent la même
chose paraissent chacun **inutiles** (l'autre compense) — au risque de supprimer les
deux ; deux blocs qui n'agissent qu'**ensemble** se voient chacun attribuer tout le
mérite, gonflant artificiellement leur importance.

**La correction : la valeur de Shapley.** Chaque bloc est vu comme un « joueur » dont
la contribution est moyennée sur de nombreux ordres d'ajout possibles. Le mérite total
est ainsi réparti **exactement** entre les blocs, redondances et synergies comprises.
Le calcul reste économe : échantillonnage aléatoire tronqué (on s'arrête dès que le
prompt complet est reconstitué), mené sur un petit échantillon (~20 % des trajets), et
les combinaisons déjà évaluées sont resservies gratuitement par le cache.

**Before :** l'importance d'un bloc = effet de son retrait isolé → deux blocs
redondants semblent inutiles, deux blocs synergiques semblent tous deux indispensables.
**After :** l'importance = contribution moyenne équitable → la carte des blocs utiles /
nuisibles reflète les interactions réelles, et guide mieux réécritures et compactions.

---

## [2026-07-14] Calibration : entonnoir de mutation, opérateurs riches et compaction du prompt

La boucle de calibration de prompt (`scripts/prompt_calibration/`) dépense désormais
beaucoup moins d'évaluations LLM pour progresser davantage, et sait **raccourcir** le
prompt sans dégrader le score.

**Un entonnoir au lieu d'une mutation à l'aveugle.** À chaque tour, le modèle de
mutation propose maintenant **plusieurs pistes en un seul appel**. Elles franchissent
un entonnoir qui n'évalue au prix fort que ce qui le mérite :
- **Tabu** — une piste quasi identique à une modification déjà tentée et rejetée est
  écartée immédiatement, sans aucune évaluation. Elle redevient tentable plus tard,
  une fois que le prompt a suffisamment évolué.
- **Pré-sélection rapide** — les pistes restantes sont comparées sur un petit
  échantillon (~20 % des trajets) ; seule la meilleure passe l'évaluation complète et
  le test statistique.

**La boucle apprend quels leviers marchent.** Un bandit choisit l'opérateur à
privilégier (réécrire, supprimer, insérer, déplacer, fusionner, condenser, scinder un
bloc) en fonction de ce qui a été accepté jusqu'ici — visible au dashboard.

**Le prompt est activement raccourci.** Périodiquement et en fin de campagne, une passe
de **compaction** retire les blocs qui n'apportent rien, à condition de prouver
statistiquement que le score ne se dégrade pas. Comme le prompt calibré est envoyé à
chaque décision d'itinéraire en production, chaque mot économisé est payé des millions
de fois.

**Before :** chaque itération = une mutation évaluée sur tout le train, prompt qui ne
fait que grossir.
**After :** plusieurs candidats filtrés à bas coût par tour, opérateurs arbitrés
automatiquement, et un prompt qui se raccourcit tant que le score tient.

---

## [2026-07-14] Calibration : loss ordinale (EMD/JSD) et acceptation statistique

La calibration de prompt (`scripts/prompt_calibration/`) mesure et accepte désormais
plus juste.

**Loss v2 (`emd_jsd`, au choix via `loss:` dans la config).** L'ancienne loss L1
traitait toutes les tranches comme interchangeables : rendre les 15-19 ans un peu trop
adeptes du bus vers les 20-24 ans coûtait autant que vers les 50-54 ans. La nouvelle
loss respecte l'ordre des tranches — âge et distance sont mesurés par **EMD** (coût de
déplacement le long de l'axe), un décalage vers une tranche voisine coûte moins qu'un
décalage lointain. Les critères sans ordre (occupation, genre, motif, global) passent
à la **divergence de Jensen-Shannon**, et chaque strate compte désormais au prorata de
son effectif au lieu d'être ignorée sous 5 individus.

**Acceptation statistique (bootstrap).** Une mutation n'est retenue que si son gain est
**significatif** : un rééchantillonnage des agents (bootstrap apparié) estime si
l'amélioration tient au-delà du bruit d'échantillon. Le recuit assouplit l'exigence de
significativité en début de campagne (exploration) mais **jamais le signe** — une
mutation qui dégrade le score n'est plus jamais acceptée. Les rejets « pour bruit » sont
tracés (`rejected_stat`) et renvoyés au mutateur.

**Backtest sans réappel LLM.** `calibrate backtest --metrics l1_composite,emd_jsd`
recalcule n'importe quelle loss sur tout l'historique déjà stocké (les décisions brutes
sont conservées) et compare les trajectoires — on choisit la loss en connaissance de
cause avant de basculer une campagne.

**Avant :** score L1 aveugle à l'ordre des tranches ; une mutation acceptée dès que le
composite baissait, même d'un poil sous le bruit.

**Après :** l'erreur reflète la distance réelle entre tranches ; seules les
améliorations statistiquement solides sont conservées, et toute loss est rejouable
rétroactivement sur l'historique.

---

## [2026-07-13] Dashboard de calibration : l'historique d'une campagne, explorable en direct

Le moteur de calibration de prompt (`scripts/prompt_calibration/`) a désormais un
**dashboard Streamlit**, lecteur pur du store SQLite, rafraîchissable pendant qu'une
campagne tourne. On y explore toute l'histoire d'une campagne sans notebook :

- **Timeline** : chaque mutation depuis l'origine avec son verdict et son score
  composite *et* par dimension, filtrable, avec la courbe du meilleur score ;
- **DAG** : le graphe de lignée des prompts coloré par score — un clic sur un nœud
  ouvre son prompt, le diff avec son parent, ses scores et sa carte d'ablation ;
- **Distribution** : parts modales actuelles vs cible EMC² et pires croisements
  strate × mode, reconstruits depuis les décisions brutes (aucun appel LLM) ;
- **Run** : itération, meilleur score, modèles/températures, volumétrie d'éval ;
- **Maintenance** : lance les commandes `status` / `export` / `import` directement
  depuis la page — statut lisible, export téléchargeable, et import d'un ancien run
  (protégé par une confirmation, car il écrit dans l'historique).

Lancement : `calibrate dashboard --config run.yaml`. Chaque vue a son lien
partageable (`?view=DAG`). Au passage, `--config`/`--branch` s'acceptent désormais
aussi bien avant qu'après la sous-commande (`calibrate dashboard --config run.yaml`
fonctionne, avant il fallait `calibrate --config run.yaml dashboard`).

**Avant :** l'historique d'une campagne se lisait au mieux via l'export CSV/Markdown
ou en rejouant le notebook ; la progression d'un run se suivait dans les logs.

**Après :** une page web unique montre chaque mutation moins de 30 s après son
verdict et rend tout l'historique d'un run terminé explorable (timeline, DAG,
distributions) sans rien recalculer.

---

## [2026-07-13] Météo par persona : les lots LLM mélangent enfin les conditions

La météo (et le contexte trafic) est désormais **attachée à chaque persona** au lieu
d'un unique préambule commun en tête de requête. Conséquence directe : des demandes
de **météos différentes peuvent maintenant être fusionnées dans un même appel LLM**,
chaque persona gardant sa propre météo dans le prompt.

**Avant :** la météo était un paramètre de la requête ; comme le regroupement en lots
ne fusionne que des requêtes de paramètres identiques, deux agents sous des météos
différentes partaient dans des appels LLM séparés. Le micro-batching était bridé par
la météo, d'où des lots plus petits et plus d'appels.

**Après :** la météo voyage dans le bloc de l'agent. Le regroupement ne la voit plus,
donc il fusionne des agents quelle que soit leur météo ; le prompt affiche
`**Contexte :** …` sous l'en-tête de chaque persona (sa météo propre). Lots plus
pleins, moins d'appels, pour un débit et une pression de rate-limit meilleurs.

- **Décisions inchangées** : chaque persona voit exactement la même météo qu'avant,
  juste attachée à son bloc plutôt qu'en préambule — seul le **remplissage des lots**
  change.
- **Fidélité de calibration** : le pipeline de calibration applique le même format
  d'injection par persona, donc la mesure reflète le prompt réellement envoyé.

---

## [2026-07-13] Lancer la calibration du prompt depuis l'IHM GAMA

Un bouton **« Lancer la calibration du prompt »** apparaît dans l'interface GAMA
(catégorie *Calibration* des paramètres de l'expérience `e`). Il déclenche une
campagne de calibration en tâche de fond dans le contrôleur, sans quitter la
simulation ni la ligne de commande. Un paramètre **« Calibration - cycles
(itérations) »** (1–200) règle le nombre d'itérations de la boucle.

**Avant :** la calibration ne se lançait qu'en ligne de commande, depuis l'hôte
(`python -m calibration.cli run --iterations N` dans `scripts/prompt_calibration`).

**Après :** on règle le nombre de cycles dans l'IHM puis on clique sur le bouton.
GAMA envoie `POST /calibrate {iterations}` au contrôleur, qui lance la campagne en
sous-processus détaché (un seul run à la fois) et répond immédiatement. La console
GAMA affiche l'accusé de démarrage (pid, cycles, chemin du journal) ; la sortie de
la campagne est journalisée dans `experiments/current/calibration.log`.

- **Non bloquant** : la simulation continue, le contrôleur exécute la calibration
  en arrière-plan. Une seconde demande pendant qu'un run tourne est refusée
  proprement (message `calibration_busy`).
- **Prérequis** : les jeux gelés (`calibration_datasets/<version>/`) doivent exister
  et les clés API des providers être présentes dans `.env` — sinon la campagne
  s'arrête avec une erreur explicite dans `calibration.log`.

---

## [2026-07-13] Calibration de prompt : phase 1 livrée — moteur reprenable + store SQLite

Le moteur de calibration devient un **package Python testé et reprenable à tout
moment**, piloté par une CLI, avec un historique persistant interrogeable.
Fini le notebook monolithique à globals : `scripts/prompt_calibration/calibration/`
(models, blocks, metrics, evaluation, mutation, loop, store, cli) — 65 tests verts.

- **Reprise sans recalcul** : l'historique complet (prompts, mutations, évals,
  ablations) vit dans un unique store SQLite `calibration.db` où chaque prompt est
  un nœud d'un DAG identifié par le hash de son texte (comme un commit git). Tuer
  le process en pleine itération puis relancer `calibrate resume` repart
  exactement à l'itération suivante — les évals déjà calculées sont servies par le
  cache, les mutations déjà jouées rejouées à l'identique : **zéro appel LLM
  redondant**. L'init (run initial + ablation) n'est refaite que si on part de zéro.
- **Décisions brutes conservées** : chaque éval stocke ses choix modaux
  `(agent_id, mode)`, donc toute métrique future (loss v2 en phase 3) est
  recalculable rétroactivement sans réappel LLM.
- **CLI** : `calibrate run | resume | status | export | import`. `export` produit
  une vue lisible (`nodes.csv`, `mutations.csv`, `history.md`) ; `import` récupère
  les anciens runs (`mutations.jsonl` + historique) dans le nouveau store.
- **Configuration par fichier** : tout paramètre passe par un `RunConfig` (YAML),
  plus aucun global mutable.
- **Jeux val/test nettoyés de la mémoire** (fin de phase 0) : la section
  `**Historique :**` (souvenirs STM/LTM, spécifique au run source et non
  reproductible) est retirée des personas des jeux val et test à leur génération —
  la mesure de référence ne dépend plus que du profil, de la météo et des options
  de trajet. Le train la conserve (il ne sert qu'à la boucle).

**Avant :** calibration dans un notebook (état invisible, non testable) ; une
interruption imposait de relancer depuis un checkpoint approximatif ; historique
éparpillé en CSV/JSONL non reliés
**Après :** moteur importable et testé, reprise exacte au point d'arrêt via un
store SQLite, historique complet requêtable en SQL et exportable

---

## [2026-07-13] Calibration de prompt : phase 0 livrée — mesure fiabilisée

La refonte de l'outil de calibration démarre dans un nouveau package,
`scripts/prompt_calibration/` (l'ancienne version notebook est conservée intacte
dans `scripts/models_influence/`). La phase 0 du ticket 004 est livrée : la mesure
sur laquelle toute l'optimisation repose est désormais fiable.

- **Métadonnées exactes** : les attributs de scoring (genre, âge, occupation,
  taille du ménage) proviennent de la jointure `agent_id → population_N.json`,
  plus du parsing du texte. Le genre vient de `traits_json.gender` — fin de
  l'inférence par prénom et de ses erreurs connues.
- **Dérive de format résorbée** : les deux formats d'en-tête de logs
  (`--- agent_id=… ---` courant et `--- PERSONA … ---` legacy) sont parsés,
  et le journal est lu correctement même en JSON pretty-printed concaténé.
- **Jeux gelés train/val/test** : affectation stable par `sha256(agent_id)`,
  versions figées avec manifest (hash des sources, effectifs par strate) et
  rapport de couverture des marginales Cerema (strate manquante = warning).
- **Température d'évaluation minimale** (`EVAL_TEMP = 0.0`).

**Avant :** genre parfois faux (heuristique prénom), logs récents non parsables
(0 % de rattachement), jeux rééchantillonnés à chaque run
**Après :** 100 % des 720 sections de `experiments/current` rattachées à leurs
métadonnées exactes (vérifié par `check_phase0.py`), jeux reproductibles et gelés

---

## [2026-07-13] Calibration de prompt : documentation et plan d'industrialisation

Le module de calibration de prompt (`scripts/models_influence/prompt_calibration.ipynb`)
dispose désormais d'une documentation d'architecture (`docs/arch/prompt_calibration.md`)
et d'un plan de refonte en 8 phases (`docs/tickets/ticket_004_prompt_calibration_industrialisation.md`) :
mesure fiabilisée (métadonnées structurées, jeux gelés train/val/test), store SQLite
git-like reprenable, dashboard Streamlit, loss ordinale EMD/JSD, acceptation
statistique, attribution de crédit Shapley, branches parallèles avec merge,
minimisation du prompt à score constant (économie de tokens en production), et revue
de littérature scorée (GEPA, HiveMind, MAPGD, MASS, MARS, RePrompt…).

Deux anomalies documentées au passage : le genre des personas est inféré du prénom
alors qu'il existe dans `traits_json.gender` de la population générée, et le format
d'en-tête des logs récents (`--- agent_id=… ---`) ne correspond plus au regex de la
lib (`--- PERSONA … ---`) — corrections planifiées en phase 0 du ticket.

---

## [2026-07-11] Fin des HTTP 413 groq : capacité par requête vérifiée avant l'envoi

Sur le run du 2026-07-11, 38 des 63 erreurs LLM étaient des 413 « request too large »
sur les providers groq : le free tier rejette toute requête unique dont
`prompt + max_tokens` dépasse le TPM, et deux providers (`groq_openai_120/20`,
plafond 8 000) partaient sans aucun clamp — `groq_openai_120` n'a servi qu'un seul
batch sur tout le run malgré 30 RPM de quota disponible.

- Tous les providers groq déclarent désormais `max_tokens_per_request` (= leur TPM),
  qui borne aussi la taille des batchs constitués.
- Le `max_tokens` envoyé est rogné d'après la taille **réelle** du prompt rendu
  (l'estimation statique sous-évaluait les prompts de réflexion d'un facteur 2).
- Si même la sortie minimale ne tient plus, le batch est rerouté vers un autre
  modèle **avant** l'appel HTTP (nouveau compteur `llm_capacity_reroute_total`).

**Avant :** requêtes condamnées envoyées quand même — 413, retries brûlés, cascades
« providers saturés », capacité groq quasi inutilisée
**Après :** zéro 413 évitable, la capacité groq (~90 RPM cumulés) redevient
exploitable pour résorber le backlog de planification

---

## [2026-07-11] Réflexions STM ordonnancées en EDF avec garantie < 12 h simulées

Les réflexions STM partaient en fire-and-forget vers le gateway dès leur déclenchement
et se battaient avec les planifications de trajets aux heures de pointe : sur le run du
2026-07-11, 219 réflexions perdues (timeouts 120 s, providers saturés) et l'essentiel
des 411 ERROR du log. Elles passent désormais par la file EDF avec une échéance en
temps simulé de 12 h (`stm_reflection_deadline_sim_s`).

- Les planifs urgentes passent d'abord ; les réflexions remplissent les creux et
  remontent en priorité à l'approche de leur échéance.
- La contre-pression prédictive compte leurs échéances : si le débit LLM ne permet
  plus de les tenir, le `/sync` est retenu et le temps simulé se fige le temps de
  drainer — la garantie 12 h simulées est structurelle.
- Un échec gateway ne repousse pas l'échéance : la re-soumission au sync suivant
  garde la deadline d'origine, donc la priorité monte à chaque retentative.
- Nouvelle alarme `[ALARME]` (visible via `make error`) si une réflexion dépasse
  quand même son échéance simulée.

**Avant :** réflexions en concurrence frontale avec les planifs, échecs massifs
silencieusement retentés sans limite de retard
**Après :** réflexions servies dans les creux de charge, avec échéance simulée
garantie de 12 h et alarme en cas de dépassement

---

## [2026-07-11] Micro-batching réellement exploité : le ratio agents/prompt décolle

Le micro-batching regroupait très peu (2,4 agents/prompt sur le run du 2026-07-10,
57 % des prompts partaient avec un seul agent) alors que Mistral, qui porte 64 % du
trafic, plafonne à 20 agents/prompt. Quatre correctifs s'attaquent à la cause :

- **Seuil de dispatch découplé du plus petit provider** : le dispatch immédiat se
  déclenchait dès 1 tâche en file (min des providers, tiré vers 1 par les petits TPM
  Groq), court-circuitant la fenêtre d'accumulation. Le seuil est désormais une cible
  de batch (`batch_target_agents`, 10) ; en dessous, la fenêtre d'accumulation joue.
- **Fenêtre d'accumulation élargie** : 1 s → 3 s, calée sur l'inter-arrivée mesurée
  des prompts (p50 = 1,4 s).
- **Capacités de batch recalibrées sur les tokens réels** : le calcul supposait
  6 296 tokens/agent alors que le mesuré est ~1 600 ; avec 3 000 (marge 25 %), les
  providers bornés par le TPM acceptent des batchs 2 à 4× plus gros
  (groq_llama4 : 4 → 10, groq_llama3 : 1 → 4, cerebras : 4 → 5).
- **Concurrence Mistral réduite (5 → 3 workers)** : cinq workers se disputaient la
  file et la vidaient en pops d'une tâche ; moins de workers = pops plus gros, même
  débit (RPM 90 loin d'être saturé).

**Avant :** ~2,4 agents/prompt (médiane 1), batching accidentel uniquement quand le
backlog s'accumulait ; system prompt (~900 tokens) dupliqué dans chaque requête.
**Après :** les tâches compatibles s'accumulent jusqu'à 3 s ou 10 tâches avant envoi,
puis le worker remplit le batch à la capacité réelle du provider — moins de requêtes,
moins de tokens dupliqués, plus de marge RPM pour les pics (moins de 429/fallbacks).
Contrepartie : +3 s de latence max par décision, négligeable devant l'appel LLM (2-10 s).

À surveiller au prochain run : le panneau « Ratio batching (agents/prompt) » du
dashboard LLM Gateway, et les `ProviderParseError` sur les gros batchs (un batch
de 20 en échec = 20 agents à rejouer).

---

## [2026-07-11] Limitation documentée : cache OTP raté d'un jour simulé à l'autre

La clé du cache OTP persistant inclut la date simulée absolue, calculée avant le
remapping `gtfs.fixed_day`. Conséquence : même avec `fixed_day` actif (requêtes OTP
identiques d'un jour à l'autre), un cache réchauffé au jour J est intégralement raté
au jour J+1. La limitation est maintenant documentée dans `docs/arch/cache-memory.md`
et un TODO est posé dans `OtpPersistentCache.make_key` (aligner la partie date de la
clé sur la date fixe ou le jour de semaine, comme le cache OSMnx). Aucun changement
de comportement pour l'instant.

---

## [2026-07-10] Dashboard Métier Mobilité : ponctualité des départs

Nouvelle row « Ponctualité des départs (phase live) » dans le dashboard
« 07 · Métier Mobilité » : elle répond d'un coup d'œil à « les agents
partent-ils à l'heure ? » :

- **Départs à l'heure** vs **en retard** (seuil : action poussée vers GAMA
  plus de 60 s après l'heure prévue), avec le **% de départs à l'heure** ;
- pour les retardataires : **retard moyen** et **retard max** du run ;
- **départs ratés** : la planification (réponse LLM) est arrivée si tard que
  même l'heure d'arrivée prévue était déjà passée ;
- **sans réponse LLM** : activités parties sur l'itinéraire par défaut faute
  de réponse à temps (saturation/timeout) ;
- un graphique temporel « à l'heure / en retard / ratés » par tranche de 10 min.

Le bootstrap (/init) est exclu : il pré-calcule les itinéraires et ne mesure
pas de vrais départs.

**Before :** la ponctualité se reconstruisait après coup via `/debug-run`
(logs LATE) ; aucun indicateur live de retard moyen/max ni de départs ratés.
**After :** l'état de ponctualité des agents est visible en continu dans le
dashboard métier, seuils colorés (orange dès 10 retards ou 5 min de retard moyen).

---

## [2026-07-10] Dashboard LLM Gateway : panneaux providers lisibles et « Réactivation dans (s) » réparé

Trois lisibilités corrigées sur le dashboard « 04 · LLM Gateway » :

- **État des providers** : chaque tuile affiche maintenant le nom du provider
  au-dessus de son état (Actif, Cooldown, …) — plus besoin de deviner quelle
  tuile correspond à quel provider.
- **Réactivation dans (s)** : le panneau restait à 0 même quand un provider
  était en cooldown, car la métrique ne couvrait que la désactivation
  temporaire (erreurs consécutives), pas le cooldown 429/5xx — de loin le cas
  le plus fréquent. La métrique expose désormais le TTL restant quel que soit
  le mécanisme.
- **Tokens cumulés par provider & modèle** : les barres étaient légendées avec
  le jeu de labels Prometheus brut (`{instance=…, job=…, model=…, provider=…}`) ;
  elles affichent maintenant `provider · modèle` (ex. `google_gemini31 ·
  gemini-3.1-flash-lite-preview`).

**Before :** un provider en cooldown affichait « Réactivation dans 0 s » ;
états et tokens illisibles sans survoler chaque série.
**After :** le compte à rebours de réactivation est correct pour cooldown et
désactivation ; provider identifiable d'un coup d'œil sur les trois panneaux.

---

## [2026-07-10] Dashboard Métier Mobilité : graphiques en heure simulée

Les trois graphiques temporels du dashboard Grafana « 07 · Métier Mobilité »
(parts modales dans le temps, trajets par motif, états des agents) affichent
désormais l'**heure de la simulation** sur l'axe X, au lieu de l'heure réelle.
La lecture métier devient directe : un pic voiture à 8h correspond bien à 8h
du matin *vécu par les agents*, quelle que soit la vitesse d'exécution du run.

**Before :** l'axe X montrait l'heure réelle du poste ; avec une simulation
accélérée (ou ralentie par le backpressure), impossible de relier un pic modal
à un moment de la journée simulée.
**After :** l'axe X suit `gama_sim_logical_time_seconds` — les courbes se lisent
en heures de la journée simulée. La plage temporelle sélectionnée en haut de
Grafana reste en temps réel ; restreindre la plage au run courant si plusieurs
runs sont couverts (l'axe repartirait en arrière à chaque /init).

---

## [2026-07-10] Répartition LLM proportionnelle à la capacité réelle et réservation TPM à la taille exacte

Le load balancer distribue désormais les requêtes proportionnellement à la capacité
**effective** de chaque provider (`min(RPM, TPM/3000)`), et la fenêtre TPM glissante est
recalée sur la taille réelle de chaque requête (prompt mesuré en caractères / 3, puis
tokens facturés) au lieu d'un forfait fixe de 3 000 tokens.

Ce que ça débloque :
- **Les gros providers absorbent enfin leur part** : mistral passe de ~8 % à ~49 % de la
  rotation (il détient 47 % de la capacité totale) ; la flotte Groq bridée à 6-12k TPM
  descend à 1-2 % chacun au lieu de saturer.
- **Fin du sous-comptage des grosses requêtes** : une réflexion STM (~4 500 tokens_in/agent,
  2× le forfait) réserve son vrai coût — c'est ce sous-comptage qui produisait des
  violations TPM (groq_qwen mesuré à 122 % de son quota) et des 429.
- **Les petites requêtes rendent leur headroom** : un batch plus léger que le forfait
  libère immédiatement la différence pour les autres workers.
- Un WARNING signale toute requête dont le coût réel dépasse l'estimation de +25 %
  (dérive du ratio caractères/tokens, mesuré à 3,05-3,50 sur run réel).

**Before :** mistral utilisé à 7 %, groq_qwen à 122 % de son TPM, 29 % des minutes actives
avec des 429, réflexions STM abandonnées en masse (« providers saturés »).
**After :** rotation alignée sur les quotas ; la fenêtre TPM reflète la consommation réelle
requête par requête.

---

## [2026-07-10] Réduction des fallbacks LLM : throttling de concurrence et timeouts étendus

Baisse drastique du fallback LLM (6.8% → ~0%) via throttling de la concurrence et tolérance accrue aux 5xx.

**Changes :**
- `worker_concurrency`: 20 → 8 (60% moins de requêtes parallèles, réduit la saturation des providers)
- `remote_llm_poll_timeout`: 60s → 120s (double du temps d'attente avant fallback, absorbe cooldowns 5xx)
- Google Gemma 42/43: `concurrency_limit` réduit à 1, `disable_timeout` augmenté à 180s (plus patient après erreur)

**Before :** 254/3753 trajets (6.8%) en fallback, backlog p95 = 963s, 9 rate-limits 429, Google 500 systématiques.
**After :** Pipeline moins saturé, providers moins overwhelmés, meilleure absorption des cooldowns transitoires.

---

## [2026-07-10] Refonte des dashboards Grafana : 8 vues par question, alertes et alarmes visibles

Les 5 dashboards historiques (cockpit, bottleneck, llm_agents, business, system) sont remplacés
par 8 dashboards numérotés par cycle de vie — `01_cockpit` (le run va-t-il bien ?),
`02_init_bootstrap`, `03_pipeline_scheduling`, `04_llm_gateway`, `05_routing`, `06_cache_llm`,
`07_metier_mobilite`, `08_systeme` — reliés par un menu déroulant commun. Le live ne garde que
les indicateurs actionnables pendant le run ; l'analyse fine reste dans `/debug-run`.

Ce que la refonte débloque :
- **Les alarmes `[ALARME]` sont enfin visibles dans Grafana** (compteur `alarme_total{source}`,
  feu « santé globale » dans le cockpit) et **7 alertes Grafana provisionnées** couvrent les cas
  critiques (agents bloqués, fallback LLM >10 %, aucun provider actif, drainage prolongé…).
- **La couverture du cache Qdrant** (`llm_cache_points_*`, agents couverts) répond en un coup
  d'œil à « le cache est-il assez peuplé pour l'init ? » (dashboard 02).
- **Le coût est suivi en tokens** : tokens/heure simulée, tokens économisés par le cache (04, 06).
- **Nouvelle lecture métier** : parts modales dans le temps, mode × motif d'activité
  (`trip_mode_by_purpose_total`, couvre LLM + cache + mono-choix), les 7 tranches de distance
  (les trajets 10-20 km et 20-50 km étaient invisibles), palette officielle des modes appliquée.
- **CPU/RAM par conteneur** via cAdvisor (dashboard 08) — on voit désormais *qui* consomme.
- **Toutes les vagues du bootstrap sont visibles** (`agent_bootstrap_wave_moves{wave,status}`,
  dashboard 02) : 8 lignes, une par vague, chacune avec progression, agents traités/obtenus/
  planifiés et cache hit % — seule la vague 1 était détaillée auparavant.
- Panneaux cassés corrigés : PromQL invalide sur les tokens par modèle, latence OTP par instance
  (label `instance` → `otp_instance`, il était écrasé par Prometheus), famille EDF/backpressure
  et OSMnx (ok/err/latence) enfin affichées.

**Before :** 5 dashboards accumulés, panels vides (PromQL invalide), alarmes visibles uniquement
via `make error`, tranches 10-50 km absentes, aucun coût en tokens ni vue par conteneur.
**After :** 8 dashboards par question, alertes provisionnées, feu santé + compteur d'alarmes,
coût en tokens, couverture cache Qdrant, mode × motif, CPU/RAM par conteneur.

`/debug-run` affiche en plus le ratio de choix d'itinéraire par défaut rapporté aux seules
décisions LLM (erreur définitive), avec alarme au-delà du seuil. Les métriques SDK dupliquées
(`llm_tasks_*`, `llm_mode_chosen_total`, `llm_index_chosen_total`) sont supprimées ; la latence
`/sync` est mesurée (`controller_sync_duration_seconds`).

---

## [2026-07-10] Nettoyage du code mort de la gateway LLM

Suppression du client HTTP legacy et des brouillons de prompts qui ne servaient plus, désormais
que la chaîne de production passe entièrement par le SDK typé (`LLMGatewayClient` / `TaskResult`).

**Supprimé :** `client.py` (ancien `LLMClient` sync) et ses tests dédiés (`test_client_validate.py`,
`test_e2e.py`), l'orchestrateur manuel `test_main.py` qui les pilotait, et trois variantes de
template jamais chargées (`itinary_multi_agent{2,3,4}.md.j2` — le moteur ne résout que
`itinary_multi_agent`). Aucun impact sur la simulation : ces éléments n'étaient référencés que
par eux-mêmes.

**Conservé :** les shims de compatibilité `settings/models.py` et `tasks/llm_config.py`, toujours
utilisés par les notebooks d'analyse externes.

---

## [2026-07-10] Moins de fallbacks LLM : timeout élargi, bascule de modèle sur erreur, rafale de bootstrap lissée

Quatre changements pour récupérer les itinéraires qui retombaient inutilement sur le plan
par défaut (« itinéraire le plus rapide » non arbitré par le LLM) lors des pics de saturation.

**1. Timeout de tâche LLM porté de 30 s à 60 s.** La fenêtre d'attente du controller était
trop courte face au temps de récupération de la gateway : un provider en cooldown 60 s après
une 5xx « disparaissait » avant que le client puisse réessayer. Avec 60 s, le worker a le temps
d'absorber le cooldown + backoff ou de basculer sur un autre modèle avant l'abandon.

**2. Bascule automatique de modèle sur erreur non récupérable.** Sur une réponse illisible
(hors-schéma) ou un 4xx non lié au rate-limit, le batch n'échoue plus sèchement : le modèle
fautif est mis en cooldown court et la requête est rejouée sur un **autre** modèle via la
rotation. Un JSON invalide sur un provider peut ainsi réussir sur un autre.

**3. Rafale de bootstrap lissée.** Au démarrage, les ~centaines d'agents ne lancent plus leur
premier itinéraire tous en même temps : un plafond de concurrence (`bootstrap_concurrency`,
défaut 30) étale les calculs OTP+LLM en vagues, ce qui évite la cascade de 429/5xx qui générait
des centaines de fallbacks au pré-calcul.

**Avant :** un pic de 500 (ex. « 10 tâches échouées d'affilée, error 500 ») → ~460 agents en
fallback au pré-calcul.
**Après :** la rafale est lissée, les erreurs transitoires sont réessayées sur un autre modèle,
et le client attend assez longtemps pour bénéficier de ces reprises.

**4. Rappel : le plafond `max_tokens` (400) porte sur les tokens de sortie** (complétion), pas
sur le prompt — la limite est apprise puis le batch rejoué avec un budget réduit.

---

## [2026-07-10] Cockpit init : compteur d'activités ratées fiable, couverture cache tracée, avancement bootstrap détaillé

Trois améliorations du **Cockpit — Pilotage Simulation** autour de la phase d'initialisation.

**1. « Activités ratées faute de LLM » reste à 0 pendant l'init.** Le pré-calcul des
itinéraires (bootstrap) faisait déjà de vraies décisions LLM : quand la gateway saturait,
les fallbacks étaient comptés comme des activités ratées **avant même le démarrage**. Les
décisions sont désormais taguées `phase` (`bootstrap` / `live`) et le cockpit ne compte que
la phase `live`.

**Avant :** le compteur montait à plusieurs centaines pendant l'init (fallbacks du bootstrap).
**Après :** 0 avant le démarrage, il ne s'incrémente qu'une fois la simulation en marche.

**2. Pourquoi le cache LLM n'est pas à 100 % à l'init — tracé.** Ce n'est **pas** un problème
de taille (Qdrant n'a pas de plafond) mais de **couverture** : la moitié des agents n'avait
jamais eu sa 1ᵉʳ activité stockée, car le cache n'écrit que sur appel LLM réussi (déficit
auto-entretenu si la gateway sature au peuplement). Une ligne de couverture au démarrage
(`[cache] couverture LLM … N points, A agents couverts, S obsolètes`) + des gauges Prometheus
+ une classification des miss (*agent absent* vs *clé différente*) rendent la cause lisible.
Un `[ALARME]` signale les points hérités d'un schéma obsolète (`weekday=None`) qui gonflent
la base sans jamais servir.

**3. Avancement du bootstrap (phase 4) visible en direct.** Nouvelle rangée cockpit avec
progression, agents planifiés, taux de hit cache du bootstrap, vague d'anticipation courante
et trajets futurs pré-cachés.

---

## [2026-06-10] Réparation JSON malformé (Mistral)

`adapters/base.py` utilise désormais `demjson3` comme fallback quand `json.loads` échoue sur la réponse d'un provider (virgule manquante, JSON tronqué, etc.). Si la réparation réussit, l'appel se termine normalement avec un log `WARNING`; sinon, la `ProviderParseError` est levée comme avant.

**Avant :** `JSONDecodeError: Expecting ',' delimiter` → tâche en échec définitif.  
**Après :** `demjson3` répare le JSON malformé et le traitement continue.

---

## [2026-06-05] Réflexions agents opérationnelles (STM/LTM)

Les agents peuvent maintenant générer et stocker des réflexions à partir de leur mémoire
courte et longue durée. Les réflexions passent par la gateway LLM (cache sémantique,
load balancing, circuit breaker) et sont prioritaires sur les départs futurs.

**Avant :** `self.llm` toujours None → toutes les réflexions silencieusement ignorées.  
**Après :** les réflexions STM et LTM sont exécutées, retournées et persistées correctement.

---

## [2026-06-05] Cache OTP activé partout par défaut

Le cache persistant OTP est désormais actif dans tous les modes sans configuration
explicite. Les itinéraires O/D/heure sont réutilisés entre les runs, ce qui accélère
significativement le warm-up.

**Avant :** certaines configs d'expérience forçaient `otp_cache_enabled: false`,
désactivant silencieusement le cache.  
**Après :** la valeur par défaut (`True`) fait foi ; les 36 configs d'expérience ne
peuvent plus le désactiver par inadvertance.

---

## [2026-06-05] Observabilité unifiée des trois caches (OTP / OSMnx / LLM)

Une seule ligne de log `[cache] OTP X% · OSMnx Y% · LLM Z%` est émise en fin de
warm-up et à chaque sync, avec le détail des miss LLM par raison (`no_candidates`,
`code_not_in_options`, …). Permet de diagnostiquer rapidement un cache inefficace.

---

## [2026-06-04] Routage population simplifié — SQLite comme unique source de vérité

Le fichier de population ne stocke plus les routes calculées. Toutes les routes passent
par le cache SQLite OSMnx, ce qui évite les désynchronisations entre le fichier et le
cache et simplifie la génération de population (`generate_population.ipynb`).

---

## [2026-06-04] Mémoire long terme agents activée

Les réflexions quotidiennes (STM→LTM) et la self-reflection multi-jours sont
fonctionnelles. La mémoire est activée par défaut ; les événements sont écrits en
double (JSONL + CSV) pour faciliter l'analyse.

---

## [2026-06-03] Météo injectée dans chaque observation agent

Les agents reçoivent les conditions météo courantes dans chaque observation.
Le flag `timed_out` est ajouté dans `GamaArrivalsLogger` pour distinguer les
agents bloqués en attente TC (> 30 min) des arrivées normales.

---

## [2026-06-03] Données versionnées avec DVC

Population (`po_toulouse.small`, `population_samples`) et sorties eqasim sont
maintenant versionnées via DVC. Les données météo historiques Toulouse 2025-01
à 2026-04 sont incluses.

---

## [2026-06-03] Throttling scheduler corrigé + robustesse initialisation

La formule de throttling (`min(cap,(n/scale)^k)`) est plus stable sous forte charge.
Les endpoints `/reflect` et `/sync` répondent `not_ready` (au lieu d'une erreur 500)
si le scénario n'est pas encore initialisé.

---

## [2026-06-15] Prompts système en source unique (prompts.yaml)

Le texte des prompts système est désormais centralisé dans
`llm_module/prompts/prompts.yaml` (fusion avec l'historique de calibration),
au lieu d'être codé en dur dans les templates Jinja. Une carte `active:` désigne
la variante en production par catégorie ; promouvoir un prompt calibré ne demande
plus de modifier le code. Le template `itinary_multi_agent` ne porte plus que la
structure (boucle agents + `{{ schema }}`). Variante active initiale : `expert`.

---

## [2026-06-15] Cache LLM invalidé au changement de prompt système

Le cache sémantique LLM est désormais partitionné par empreinte du prompt système actif :
`data/cache/llm/<checksum>/<population>/`. Le checksum
(`PromptManager.active_prompt_checksum()`) change dès qu'une nouvelle variante de prompt est
promue, évitant de réutiliser des décisions obsolètes. Les anciens caches sont conservés.

## [2026-06-17] Aucun déplacement ne démarre le week-end

Un départ planifié tombant un samedi ou un dimanche est automatiquement reporté
au lundi suivant à la même heure (samedi -> +2j, dimanche -> +1j). Le décalage
est appliqué sur le `departure_time` dans `_compute_move_for_activity`, donc
l'itinéraire OTP, `expected_arrive_at` et le `schedule_at` côté GAMA en
découlent. Comportement activable via `agent.no_weekend_departures` (défaut: vrai).

---

## [2026-06-17] Repères temporels unifiés dans les logs (`[SIM_TIMING]`)

Trois lignes de log partagent désormais le tag commun `[SIM_TIMING]` avec un champ
`event=...` pour faciliter la recherche (`grep '\[SIM_TIMING\]'` ou `grep event=SIM_DAY`),
chacune horodatée par l'heure réelle (`real_time`) :
- `event=SIM_START` : réception de `/init` (lancement de la simu) ;
- `event=INIT_DONE` : fin de la phase d'init (bootstrap terminé) ;
- `event=SIM_DAY` : à chaque tranche de 24h de temps simulé écoulé depuis le départ,
  avec `sim_day`, `sim_time` et `real_elapsed` (temps réel cumulé) pour mesurer le débit
  de la simulation.

Implémenté via `helper.format_sim_timing(...)`, appelé depuis `handle/application.py`
(`/init`) et `simulation_controller.sync()` (borne 24h).

---

## [2026-06-24] Consommation de tokens traçable par jour simulé et économie du cache

Deux ajouts pour mesurer empiriquement la consommation de tokens et l'effet du cache :

- `llm_exchanges.jsonl` porte désormais `sim_ts` / `sim_day` (timestamp simulé repris de
  `AgentSpec.departure_timestamp`), permettant de ventiler les tokens par **jour de
  simulation** au lieu de l'horloge murale.
- Chaque hit du cache sémantique LLM est tracé dans `workdir/llm_cache_hits.jsonl`
  (`log_llm_cache_hit()`). Comme un hit ne génère aucun appel — donc aucune ligne dans
  `llm_exchanges.jsonl` —, ce fichier permet de compter les appels économisés et d'estimer
  les tokens épargnés.

Le notebook `scripts/analysis/llm_traffic_analyse.ipynb` ajoute un graphe
« tokens par jour vs limite journalière » (plafond 338 540 000 tokens en pointillé),
empilé par catégorie, avec l'économie de cache estimée si `llm_cache_hits.jsonl` est présent.

---

## [2026-06-24] Réalignement des agent_id mal formés par le LLM

Le modèle renvoyait parfois un `agent_id` mal formé dans les réponses `itinary_multi_agent`
(ex. `PERSONA 446264`, ou le nom du persona à la place du numéro). Comme le démultiplexage
des résultats matche par `agent_id` exact, ces agents étaient **silencieusement écartés** :
aucune recommandation de trajet ne leur était renvoyée, et les métriques de distance/mode
les ignoraient.

- **Worker** (`worker/task_worker.py`) : après validation de la sortie LLM, chaque `agent_id`
  inattendu est réaligné sur l'identifiant réel via sa partie numérique. Un réalignement est
  loggé en `warning`, un id non résolu (sans chiffre, ex. un nom) en `error`.
- **Prompt** (`prompts/templates/itinary_multi_agent.md.j2`) : l'en-tête persona passe de
  `--- PERSONA {id} ---` à `--- agent_id={id} ---` (le mot « PERSONA » incitait le modèle à le
  recopier), et une consigne explicite demande de recopier l'`agent_id` numérique à l'identique.
- **Schéma** (`prompts/schemas.json`) : `agent_id` documenté (« recopier l'id fourni, numérique
  uniquement, sans préfixe ni nom »).

---

## [2026-06-26] Calibration de prompt : Gemini de bout en bout & tableau de bord de présentation

Le notebook `scripts/models_influence/prompt_calibration_V4.ipynb` et son module
`prompt_calibration_lib.py` évoluent pour produire un support de présentation lisible.

- **Modèle unifié** : évaluation **et** génération de mutations passent sur
  `gemini-3.1-flash-lite-preview` (plus aucune dépendance Mistral). `generate_mutation`
  appelle désormais l'API generativelanguage. Le log affiche explicitement le modèle
  réellement utilisé (résolu depuis `default_model` du provider).
- **Tableau de bord** (`present_calibration_state`) affiché au run initial puis à **chaque**
  mutation (acceptée ou rejetée) : carte d'ablation colorée (vert=utile/rouge=nuisible),
  méta « pires écarts strate × mode » vs EMC², score global, scores L1 par dimension,
  barres distribution actuelle vs EMC² (hachuré), et évolution du score (points verts
  conservés / rouges rejetés).

---

## [2026-06-26] Cooldown 429 : respect du délai Gemini (corps JSON)

Sur un rate limit 429, le délai de retry était lu uniquement dans les headers
(`x-ratelimit-reset-requests`). Google Gemini ne renvoie pas ce header — il place le
délai dans le corps JSON — donc le cooldown retombait systématiquement sur le défaut de
60s, en ignorant un « retry in 6.6s » bien plus court.

`adapters/base.py` extrait désormais ce délai du corps (`extract_retry_delay_from_body`) :
champ structuré `error.details[].retryDelay`, puis repli sur le texte `"Please retry in Xs"`.
Le header reste prioritaire quand il est présent. Bénéficie à la fois au worker (durée de
cooldown du provider) et au notebook de calibration (qui lisaient tous deux le même attribut
`ratelimit_reset`).

---

## [2026-07-07] llm_module : 4 correctifs de fiabilité (batching, timing, circuit breaker)

Relecture complète du module → correction de quatre bugs :

- **Déclenchement des batchs (race condition)** : l'armement du compte à rebours reposait
  sur `queue_size == 1` ; deux requêtes simultanées sur une file vide pouvaient chacune
  observer une taille de 2 et aucune n'armait le dispatch (tâches bloquées jusqu'au timeout
  client). Un flag SETNX `batch_sched:{batch_key}` garantit désormais exactement un dispatch
  différé par cycle de batch ; le worker le libère au moment du pop (TTL en filet de sécurité).
- **`min_tpm_required` perdu** : le re-dispatch d'une file non vide après un batch réussi
  omettait la contrainte TPM — les tâches suivantes pouvaient partir vers un provider
  sous-dimensionné. L'argument est maintenant propagé.
- **Métrique `P4_4_ms` toujours à 0** : l'attente micro-batch était calculée en mélangeant
  `time.monotonic()` (uptime) et un timestamp epoch — résultat négatif clampé à 0. Calcul
  corrigé avec `time.time()`, et migration de `datetime.utcnow()` (naïf, déprécié) vers
  `datetime.now(timezone.utc)` dans les modèles et le worker.
- **Circuit breaker Google inopérant sur timeout** : l'adapter Google levait ses erreurs
  (timeout, réponse vide/bloquée) avec le nom de classe `"google"` au lieu du nom d'instance
  (`google_gemma42`, …) — le cooldown était posé sur une clé que personne ne consultait et
  l'instance fautive restait sélectionnée. Les exceptions portent désormais `_instance_name`.

## [2026-07-07] llm_module : restructuration en package (ports & adapters)

Mise en œuvre du CR [llm-module-package-refactor.md](arch/llm-module-package-refactor.md)
(phases 0 à 5). Le contrat HTTP consommé par GAMA est inchangé.

- **Packaging** : `pyproject.toml` (installable `pip install .`), 12 dépendances runtime au
  lieu de ~45 — image Docker du gateway fortement allégée. Extras `[test]` et `[monitoring]`.
- **Plus d'effets de bord à l'import** : Settings construits explicitement (`get_settings()`),
  fabriques `create_app()` / `create_celery_app()`, reset des fenêtres RPM déplacé dans le
  lifespan de l'API (un redémarrage de worker ne remet plus les quotas à zéro), suppression
  du couplage caché `from settings import settings` dans la télémétrie.
- **Découpage du broker** : `redis_broker.py` (~30 fonctions libres) remplacé par 4 classes
  (`RedisTaskStore`, `RedisRateLimiter`, `RedisBatchQueue`, `RedisMetricsSink`) derrière des
  interfaces Protocol (`ports/`), avec équivalents `InMemory*` pour tester sans Redis.
- **Perf** : compteurs worker migrés vers un hash Redis (`wmetrics`) — 1 `HGETALL` par scrape
  Prometheus ; adapters mis en cache avec client httpx partagé (keep-alive entre appels LLM) ;
  clé API Google en header `x-goog-api-key` (plus de clé dans les URLs de logs).
- **SDK typé** : `LLMGatewayClient.execute()` → `TaskResult` pydantic (fini les dicts bruts,
  `"EXPECTED_ERROR"` et clés `_post_ms` injectées) ; `llm_agent.py` migré. L'ancien `LLMClient`
  reste pour les tests E2E.
- **Frontières vérifiées** : `core/` pur (batching, SWRR) + contrats import-linter en CI
  possibles (`lint-imports --config llm_module/pyproject.toml`).
- Tests : 197 unitaires verts (52 ajoutés). À rejouer avant merge : `docker compose build`
  + `test_e2e.py --burst 20`.

## [2026-07-07] llm-agents : correctifs de fiabilité (revue de code)

Quatre corrections issues de la relecture complète du module `llm-agents` :

- **Boucle d'envoi WebSocket robuste** : le handler d'exception de `publish_loop`
  référençait un attribut inexistant (`self.reconnect_interval`) — toute exception
  générique tuait définitivement la boucle d'envoi des actions bootstrap vers GAMA.
- **Worker de fallback annulé sur ré-init** : `set_scenario` annulait le wrapper
  `start_worker` (déjà terminé) au lieu de la vraie boucle de scan ; sur des `/init`
  successifs, l'ancienne boucle continuait de scanner l'ancienne population. Nouveau
  `stop_worker()` sur le scénario, appelé avant remplacement.
- **Persistance de la mémoire long-terme réparée** : les `MemoryEntry` étaient
  sérialisées en chaînes (`json.dumps(default=str)`) — irrécupérables au redémarrage,
  la mémoire épisodique repartait de zéro à chaque restart. Sérialisation explicite
  `to_dict()`/`from_dict()` (round-trip testé), fichiers de l'ancien format tolérés,
  et correction du cleanup >10 000 entrées et de `get_user_stats` qui traitaient les
  entrées comme des dicts (TypeError).
- **Clé du cache OTP persistant complétée avec `include_bike`** : un itinéraire calculé
  pour un agent sans vélo pouvait être resservi à un agent avec vélo (option vélo
  silencieusement absente des choix du LLM). Effet de bord : les entrées existantes du
  cache OTP deviennent froides (nouveau format de clé) — le cache se repeuple au premier run.

Tests : round-trip `MemoryEntry`, save/load métadonnées LTM, annulation worker,
différenciation des clés de cache, + 16 tests unitaires existants verts.

## [2026-07-08] Fiabilité pipeline LLM : corruption cache, délais 429, alarmes

Diagnostic d'une simulation où 80 % des agents restaient inactifs (backlog de
planification à 886/901 après 1h30) : providers LLM en rate-limit, cache sémantique
à 0 % de hit, backpressure inopérant. Trois correctifs :

- **Cache sémantique LLM — accès Qdrant sérialisé** : le client Qdrant embarqué n'est
  pas thread-safe ; les lookups/stores concurrents (via `asyncio.to_thread`)
  corrompaient l'index ("operands could not be broadcast", erreurs SQLite) et le cache
  ne servait plus aucune décision. Verrou `_db_lock` autour de `query_points`/`upsert`,
  plus alarme après 5 erreurs Qdrant consécutives.
- **Délai 429 réellement pris en compte** : le gateway ignorait le header standard
  `retry-after` et `x-ratelimit-reset-tokens` (les 429 Groq portent sur les tokens),
  et le fallback corps ne matchait pas les messages Groq ("try again in 16m7.68s") ni
  les formats `h`/`ms` (quotas journaliers TPD). Le cooldown provider est désormais
  calé sur le délai annoncé (clampé à [10s, 1h]) avant re-routage vers un autre modèle.
- **Alarmes de saturation** (`[ALARME]`, niveau ERROR, visibles via `make error`) :
  backlog > 50 % de la population dans `/sync` (avec min_interval et coefficients,
  poussée aussi vers la console GAMA), tous providers saturés côté worker gateway,
  et 10 échecs de tâches consécutifs côté SDK client.

Tests : 208 tests `llm_module` verts, dont nouveaux cas de parsing (`retry-after`
brut, `reset-tokens` prioritaire, durées `2h37m12.5s`, `140ms`, `16m7.68s`).

## [2026-07-08] Backpressure /sync : seuil relatif à la population

La formule de throttling introduite le 11 juin (`min(cap, (n / (120×pop/100))^3.7)`)
rendait le frein inatteignable : le backlog ne dépassant jamais la population, le
seuil absolu (1200 pour 1000 habitants) n'était jamais franchi — 0.33s de pause avec
886/901 agents en attente. Nouvelle formule `cap × min(1, backlog/population)^k`
extraite dans `backpressure.py` (fonction pure) : ~2.3s à 50% de backlog, ~19s à 89%,
cap (30s) à pile pleine, identique quelle que soit la taille de population. Le
coefficient `min_internal_coeff_scale`, devenu sans objet, est supprimé des settings.

Tests : `tests/test_backpressure.py` (10 cas) vérifie l'invariance du délai à ratio
de remplissage égal, l'atteignabilité du cap à pile pleine, la croissance monotone
avec le backlog et le cas réel du run 2026-07-07 (886/1000 → ~19.2s).

## [2026-07-08] llm-agents : correctifs secondaires et optimisations (revue de code, suite)

Implémentation des points #5–#8 et #11–#14 de la [revue de code](revue-llm-agents-reste-a-faire.md) :

- **Fallback LTM sans ChromaDB réparé** : `_init_shared_index` référençait une variable
  jamais définie dans la branche "simple storage" (NameError au premier démarrage sans index).
- **Mode SOLARI + récursion réparé** : `do_get_iteraries_v1` n'acceptait pas `include_bike`
  (TypeError systématique quand `recursion_search_depth > 0`).
- **Plus de trajet perdu sur échec WebSocket** : le rollback de `_push_planned_move` restaure
  le move calculé (LLM + OTP), et le scan de fallback détecte l'état Idle+plan pour retenter
  l'envoi au lieu de tout recalculer.
- **Cache sémantique LLM aligné sur l'intention** : suppression du rejet par seuil de
  similarité (`below_threshold`) — le filtre déterministe (agent + activité + tranche 10 min
  + hash options/météo) identifie déjà le contexte ; la similarité ne sert plus qu'à classer
  les candidats multiples. La LTM peut évoluer entre les runs sans invalider les décisions.
- **Persistance LTM allégée** : écriture des métadonnées par rafale (debounce 30 s + flush à
  l'éviction LRU) au lieu d'une réécriture complète du fichier à chaque entrée ; sérialisation
  unique ; écritures déportées hors de l'event loop ; `print()` remplacés par loguru.
- **Requêtes LTM filtrées côté vector store** : le retriever passe un filtre `person_id`
  (clause `where` Chroma) avec `top_k×5` candidats au lieu de rapatrier jusqu'à 500 nœuds
  globaux puis filtrer en Python — le recall par agent ne dépend plus du peuplement global.
- **I/O fichier hors event loop** : les écritures CSV/JSONL par événement (moves, arrivées
  GAMA, hits du cache LLM, états d'agents) passent par `asyncio.to_thread` — plus de blocage
  des coroutines aux heures de pointe.
- **Session HTTP OSMnx réutilisée** : une `aiohttp.ClientSession` partagée (keep-alive)
  remplace la création d'une session par requête vers les réplicas osmnx.
- **Tâches de fond protégées du GC** : nouveau helper `create_background_task` (référence
  forte jusqu'à complétion) appliqué à tous les `asyncio.create_task` fire-and-forget
  (planification, push, stores de cache, reconnexion WebSocket, boucle d'envoi).

Tests : rollback push, debounce LTM, référence des tâches de fond, signatures — verts ;
16 tests unitaires existants verts.

## [2026-07-08] llm-agents : métrique minuit et hygiène des logs (#9, #10)

- **Métrique `agent_scheduling_lag_seconds` corrigée au passage de minuit** : le delta
  envoi−cible (deux horaires mod 86 400) est normalisé dans [−43 200, +43 200] — un envoi
  à 00:05 pour une cible 23:55 compte désormais +600 s au lieu de −85 800 s.
- **Logs réparés et nettoyés** : deux `logger.warning("... %s", …)` (format printf ignoré
  par loguru → message affiché littéralement) convertis en f-strings dans la préparation
  de population ; suppression des logs de diagnostic `[trace]` marqués « à retirer »
  (factory, wrapper de cache OTP, init du cache par population).

## [2026-07-08] Anti-saturation gateway : quotas journaliers, timeout 30 s, backpressure SDK

Diagnostic du run où plus aucune décision LLM ne revenait après quelques jours simulés :
les prompts grossissent avec la mémoire (≈675 → 2000 tokens), les quotas free-tier
s'épuisent et le pipeline dégénérait en timeouts/plans par défaut (jusqu'à 99 % d'échecs
LLM le dernier jour). Trois correctifs :

- **Quotas journaliers RPD/TPD appliqués** (jusque-là purement informatifs) : dès qu'un
  provider atteint son `rpd_limit`/`tpd_limit`, il est écarté de la rotation jusqu'à minuit
  UTC au lieu d'être re-sollicité toutes les `disable_timeout` secondes. Compteurs journaliers
  UTC dans Redis (requêtes à la réservation, tokens réels après l'appel) ; `/health` expose
  `daily_requests`/`daily_tokens`/`quota_exhausted`.
- **Timeout tâche LLM 90 s → 30 s** : fallback plan par défaut plus rapide, la simulation ne
  bloque plus 90 s par calcul quand la gateway est muette. Budget de saturation-retry du
  worker recalé sous 30 s.
- **Backpressure SDK sur alarme** : quand l'alarme « 10 échecs consécutifs » se déclenche,
  le client suspend les nouvelles soumissions jusqu'au drainage de la pile in-flight sous
  20 % de `worker_concurrency`, laissant la gateway respirer avant de re-charger.

Tests : quotas RPD/TPD (in-memory + Redis) et drainage backpressure verts ; suite
`llm_module` (208 tests) verte.

---

## [2026-07-08] Cache OSMnx réutilisable au rejeu

Un rejeu de simulation recalculait tous les trajets (Pass 2, ~0,4 s/route) au lieu de
frapper le cache. Deux causes corrigées :

- **Clé voiture sans date absolue** : `OsmnxPersistentCache.make_key` n'inclut plus la date
  (`YYYY-MM-DD`), seulement le **jour de la semaine + tranche horaire** — la granularité réelle
  du facteur de congestion. Deux runs à des dates calendaires différentes mais même weekday
  réutilisent les mêmes trajets. Marche/vélo restent indépendants du temps (coords + mode).
- **Échantillonnage d'agents déterministe** : la sélection aléatoire des agents depuis la
  sortie eqasim utilise désormais une seed fixe (`data.population_sample_seed`, défaut 42) via
  un RNG local. Un rejeu retire exactement le même sous-ensemble d'agents → mêmes coordonnées
  → le cache SQLite fait hit au lieu de recalculer.

Note : les entrées voiture antérieures (clé incluant la date) ne sont plus adressées et se
repeuplent au premier run.

---

## [2026-07-08] Mode drainage /sync : GAMA retenu jusqu'à vidage de la pile à 80 %

Le frein progressif du `/sync` ne retenait GAMA que ~2.3 s par step à 50 % de backlog :
le temps simulé filait devant le pipeline LLM et les agents restaient inactifs faute de
plan. Ajout d'un **mode drainage à hystérésis** (`update_drain_mode`, `backpressure.py`) :

- Enclenché quand la pile atteint `drain_trigger_ratio` (50 %), il retient chaque réponse
  `/sync` jusqu'au cap (30 s, limite du read timeout HTTP de GAMA) en ré-échantillonnant
  la pile chaque seconde.
- Relâché seulement quand la pile repasse sous `drain_release_ratio` (20 %, pile vidée à
  80 %) — entre les deux seuils GAMA reste bridé à ~1 step par cap.
- Traces `[drain]` (WARNING enclenchement/cap atteint, INFO relâchement) ; réglages dans
  `WorldConfig` (`drain_trigger_ratio: 0` pour désactiver).

Doc : `docs/arch/llm-inference.md` § « Mode drainage /sync ». Tests :
`tests/test_backpressure.py` (15 verts).

---

## [2026-07-08] Fix troncature des réponses LLM à max_tokens sur les batches

Les batches `stm_reflection` de 10 agents (~500-1800 tokens de sortie par agent)
saturaient le `max_tokens` fixe de 4096 : réponse JSON coupée en plein milieu →
`JSONDecodeError` à offset constant (char 13158/14704 ≈ 4096 tokens), et batch entier
perdu. Deux corrections dans le gateway :

- **Budget de sortie proportionnel au batch** (`task_worker._execute_batch`) : le
  `max_tokens` client est désormais un budget par tâche, multiplié par le nombre
  d'agents fusionnés, borné par le nouveau réglage `max_output_tokens` (16 384) puis
  par la capacité du provider.
- **Détection de troncature typée** (`BaseAdapter._check_openai_finish_reason`) : les
  adapters mistral/groq/cerebras/openai vérifient `finish_reason == "length"` et lèvent
  `max_tokens_truncation` (503, retryable) au lieu d'un parse error trompeur — couvre
  aussi le `content` vide des modèles thinking (GLM-4.7) dont le budget part en
  raisonnement.

Doc : `docs/arch/llm-inference.md` § « Budget de sortie proportionnel au batch ».
Tests : `tests/test_adapter_base.py` (42 verts).

Complément : la jauge `activities_to_compute_count` compte désormais les agents Idle
sans plan **en direct** (plus de snapshot figé au dernier sync) — indispensable pour que
le mode drainage voie la pile baisser pendant qu'il retient la réponse `/sync` et rende
la main dès le seuil de relâchement. Clarification doc : avec l'horizon glissant 24h,
un agent qui termine son trajet reçoit immédiatement son move suivant et passe `ready` ;
un taux d'`inactive` durable est bien le symptôme d'un précalcul en retard (et non un
état légitime), à l'exception des activités consécutives au même endroit (`legs=[]`).

Réglage de la courbe de frein (demande du 2026-07-08) : exposant `k` passé de 3.7 à
**1.5** pour un freinage précoce et progressif (~1 s à 10 % de pile, ~2.7 s à 20 %,
~5 s à 30 %, ~7.6 s à 40 %, ~10.6 s à 50 %, ~21.5 s à 80 %). Le mode drainage et
l'alarme backlog se déclenchent désormais ensemble à **80 %** (`drain_trigger_ratio`)
et se relâchent au retour sous **20 %** (`drain_release_ratio`), l'alarme n'ayant plus
de seuils codés en dur.

## [2026-07-08] Fix : cache OSMnx inactif pendant le Pass 2 de génération de population

Le cache persistant OSMnx n'était initialisé qu'**après** l'écriture du fichier
population : lors d'une régénération, le Pass 2 (calcul des temps de trajet pour
l'ajustement des plannings) recalculait toutes les routes via OSMnx sans lire ni
alimenter le cache. L'initialisation (`_init_osmnx_cache`) est déplacée en tête de
`_prepare_population`, avant tout routage : le Pass 2 lit et remplit désormais le
cache, et une régénération ultérieure réutilise les routes déjà calculées.

Doc : `docs/arch/cache-memory.md` § « cache persistant OSMnx ».

## [2026-07-08] Plafond de complétion par provider (max_output_tokens) auto-appris

Les batchs `stm_reflection` échouaient en HTTP 400 sur `groq_llama4`
(`max_tokens` calculé = 16 384 > limite de 8 192 de `llama-4-scout`). Chaque provider
porte désormais un champ optionnel `max_output_tokens` dans `providers.yaml` (plafond
de complétion du modèle) : le worker borne le `max_tokens` envoyé à cette valeur, et
le load balancer écarte les providers incapables de servir le budget de sortie d'une
tâche (filtre `min_output`, même mécanique que `min_tpm`). Si un provider répond
malgré tout 400 « max_tokens must be ≤ N », la limite N est **apprise
automatiquement** : config ajustée en mémoire, ligne écrite dans `providers.yaml`
(commentaires préservés, écriture atomique, persistée sur l'hôte via le bind mount)
et batch rejoué au lieu d'échouer définitivement.

Doc : `docs/arch/llm-inference.md` § « Plafond de complétion par provider ».

## [2026-07-08] Cockpit de pilotage Grafana

Nouveau dashboard `cockpit.json` regroupant en une page l'état de la simulation :
avancement de l'init (5 étapes), remplissage de la pile et frein backpressure,
délai réel par step, **agents bloqués** (aucune planification réussie depuis
> `world.stuck_agent_threshold_hours` h simulées, défaut 20 h), état et **quotas
jour** des providers (ratio d'usage RPD), taux de hit des caches (LLM / OTP /
OSMnx) et **dernières erreurs LLM**.

Nouvelles métriques exposées côté gateway (`llm_provider_rpm/rpd/tpd_limit`,
`requests_today`, `tokens_today`, `daily_usage_ratio`, `quota_exhausted`) et côté
contrôleur (`controller_init_stage/progress_ratio`, `backpressure_interval_seconds`,
`backlog_fill_ratio`, `drain_mode_active`, `agents_stuck`). Les messages d'erreur
bruts, non stockables dans Prometheus, transitent par un ring buffer Redis
(`llm:recent_errors`) exposé via `GET /errors/recent` et affiché grâce au plugin
Grafana *Infinity*.

Doc : `docs/arch/monitoring.md`.

---

## [2026-07-08] Fiabilité du push GAMA : rollback sur envoi non délivré + watchdog d'arrivée

L'analyse du run 15:41 a montré ~250 agents « zombies » : `send_message` avale les
exceptions WebSocket et retourne `False`, que `_push_planned_move` ignorait — le push
était annoncé réussi ([push] dans les logs) alors que GAMA n'avait jamais reçu le trajet
(3 coupures WS 1006 pendant le run). L'agent restait « en déplacement » côté Python,
inactif côté GAMA, invisible de la pile de backpressure, du drainage et du scan.

- **Rollback sur `False`** : `_direct_push` propage le booléen de `send_json` et
  `_push_planned_move` traite un retour `False` comme une exception → rollback complet,
  le scan de fallback retente le push après reconnexion (le trajet calculé n'est pas perdu).
- **Watchdog d'arrivée** : chaque push arme `heading_expected_arrive_at` ; si le temps
  simulé dépasse l'échéance de plus de `world.arrival_watchdog_hours` (défaut 1 h sim),
  le scan lève `[ALARME] Arrivée perdue`, force la fin d'activité et remet l'agent dans
  le circuit. Couvre aussi les pertes silencieuses (socket moribonde avant détection
  keepalive, message perdu côté GAMA). Métrique `controller_lost_arrivals_recovered_total`.

Doc : `docs/arch/agents-lifecycle.md` § « Fiabilité du push ».

Analyse du run 18:29 (correctifs actifs) : le rollback (67 reprises) et le watchdog
(339 agents récupérés) fonctionnent, mais les coupures WebSocket persistaient — cause
racine identifiée : **blocages de l'event loop asyncio de 7-20 s** qui faisaient expirer
le keepalive (`ping_timeout=10s`). Deux compléments :

- **`ping_timeout` porté à 60 s** (`handle/websocket.py`) : un stall ponctuel ne ferme
  plus la socket ; une vraie coupure reste détectée en ~1 min et couverte par le watchdog.
- **Moniteur d'event loop** (`controller_event_loop_lag_seconds`) : mesure en continu la
  dérive de la boucle asyncio, `[ALARME]` en ERROR au-delà de 5 s de blocage pour
  identifier l'opération synchrone fautive.

## [2026-07-09] Reset propre au remplacement de scénario (stop GAMA → nouveau /init)

Un stop de simulation GAMA ne stoppe pas le process Python (pas d'endpoint `/stop`) :
le `/init` suivant remplace le scénario. Deux résidus de l'ancien run pouvaient
contaminer le nouveau, les `person_id` étant identiques d'un run à l'autre (même
population, même seed) :

- **Tâches en vol de l'ancien scénario** : `stop_worker()` n'annulait que la boucle de
  scan — les planifications LLM/OTP déjà lancées allaient au bout et poussaient leurs
  trajets périmés à la nouvelle simulation. Toutes les tâches fire-and-forget du
  contrôleur (planification, refill, push, réflexions, checkpoints) sont désormais
  suivies dans `_inflight_tasks` et annulées en bloc au remplacement.
- **Buffer de retry du `publish_loop`** : les actions non délivrées (socket morte au
  stop) restaient en attente et étaient rejouées vers le nouveau run à la reconnexion.
  Le buffer (`LoopContainer._pending`) est purgé par `set_scenario()` avec un WARNING
  donnant le nombre d'actions écartées.

Doc : `docs/arch/agents-lifecycle.md` § « Arrêt de simulation et remplacement de scénario ».

## [2026-07-09] Ordonnancement EDF et contre-pression prédictive pilotée par les échéances

Deux causes d'effondrement des runs longs corrigées : le service FIFO du contrôleur
(un refill lointain pouvait bloquer une replanification urgente derrière un jeton de
concurrence) et un frein `/sync` aveugle aux échéances (freinait trop tard sur
épuisement de quota, et pour rien quand le backlog n'était que des refills non urgents).

- **Dispatcher EDF** (`simulation_controller.py`) : les tâches de planification sont
  servies par échéance croissante (heure de départ simulée) via une file de priorité
  (`_edf_heap`) consommée par `world.worker_concurrency` tâches, au lieu du sémaphore
  FIFO. Une replanification urgente passe devant un refill d'horizon lointain ; un push
  déjà calculé (deadline 0) passe devant tout. Flag `world.edf_enabled` (défaut `true`,
  `false` = spawn direct historique). File vidée et consommateurs annulés au
  remplacement de scénario. Le sémaphore reste utilisé par le bootstrap.
- **Contre-pression prédictive** (`backpressure.py`, `application.py`) : le `/sync`
  n'est retenu que si le test de faisabilité EDF (`edf_feasibility` : `T_k = k/D` vs
  `slack_k = (d_k − now_sim)/R`, marge `world.predictive_margin`) annonce une échéance
  menacée — vitesse maximale sinon (le frein `cap·ratio^k` est court-circuité). Le débit
  `D` est une EWMA des complétions (`ThroughputEwma`, `tau` = `world.throughput_ewma_tau_s`,
  plancher `world.throughput_floor_per_s`), le rythme `R` une EWMA du `sim_wall_clock_ratio`
  figée pendant la rétention. Le mode drainage à hystérésis reste le filet de sécurité ultime.
- **Notification GAMA** (topic `system/throttle`, hystérésis) : au-delà de
  `world.throttle_notify_threshold_s` de rétention cumulée, Python pousse le débit LLM
  réel et la vitesse de simulation, rafraîchi toutes les `world.throttle_notify_refresh_s`,
  levé au premier `/sync` sans rétention. Globales GAMA `THROTTLE_ACTIVE` /
  `LLM_RATE_PER_MIN` / `SIM_RATIO_PYTHON` (`Settings.gaml`, `LLMAgent.gaml`).
- **Observabilité** : 6 nouvelles jauges Prometheus (`controller_throughput_tasks_per_min`,
  `controller_edf_queue_depth`, `controller_t_estimate_seconds`,
  `controller_min_slack_sim_seconds`, `controller_predictive_hold_seconds`,
  `controller_deadline_misses_total`), renseignées même contrôle prédictif désactivé
  (phase d'observation pour calibrer `tau` et la marge).

Doc : `docs/arch/agents-lifecycle.md` (§ Dispatcher EDF, § Contre-pression prédictive),
`docs/arch/monitoring.md` (métriques + réglages). Tests : `tests/test_backpressure.py`
(EWMA + faisabilité EDF), `tests/test_edf_dispatcher.py` (ordre EDF).

## Outil de debug — Rapport de santé du dernier run

- **`scripts/debug/run_report.py`** : génère un rapport markdown « agent-ready » condensant
  les signaux essentiels au debug d'un run (`experiments/current` par défaut) — top erreurs/
  warnings normalisés d'`app.log`, matrice santé LLM (erreurs par provider × statut HTTP,
  taux de 429), latence pipeline (percentiles + détection de backlog), activité des agents
  (inactifs dans le temps), décisions modales & fallbacks, arrivées & timeouts. Une section
  `🚨 ALARMES` en tête synthétise les anomalies franchissant les seuils (ajustables en tête
  de script). Stdlib only, tolérant aux fichiers manquants.
- Exposé via `make report [RUN=… OUT=…]` et la skill Claude `/debug-run`.
- Limite connue : ne lit que les artefacts sur disque ; les logs des conteneurs Docker
  (api, worker, otp, osmnx) ne sont pas encore centralisés dans `app.log` (chantier suivant).

## Logging centralisé par service + analyse capacité LLM + digest live GAMA

- **Logs centralisés par conteneur** : `configure_logging()` (`llm_module/telemetry/logger.py`)
  ajoute un sink fichier `APP_WORKDIR/<SERVICE_NAME>.log` (même format qu'`app.log`) quand
  `SERVICE_NAME` est défini. `docker-compose.yml` renseigne `SERVICE_NAME`/`APP_WORKDIR` pour
  `api` (→ `api.log`) et `worker` (→ `worker.log`) ; le controller garde `app.log`. Tous
  atterrissent dans le dossier du run et sont agrégés (avec tag `[service]`) par
  `scripts/debug/run_report.py`. Sinks non-Python (`otp*`, `osmnx*`, `redis`) : via
  `docker compose logs`.
- **`scripts/debug/llm_capacity.py`** (`make capacity`, skill `/debug-run`) : analyse
  « débit vs capacité » LLM du run, 100 % à partir des logs existants — demande avant/après
  micro-batching (agents/min vs prompts/min via le champ `response` de `llm_exchanges`),
  contre-pression prédictive EDF parsée depuis `[predictive]` (débit D, pile, T d'écoulement,
  `slack_min` = temps simulé restant sur la tâche critique), épisodes `[BACKPRESSURE]` /
  `[ALARME] Gateway`, et saturation 429 par minute et par provider. Section `🚨 ALARMES`
  en tête (risque d'échéance, saturation soutenue).
- **Digest de capacité poussé à GAMA** (`handle/application.py`) : tous les 10 `/sync`, le
  controller envoie sur `system/log` une ligne synthétique `📊 [cycle N] cache LLM … · débit
  … req/min · backlog … · agents actifs/inactifs`. Signaux cheaply available en-process
  (débit `throughput_per_s`, cache `get_llm_cache_stats`, états agents) ; émission gardée
  (n'échoue jamais un `/sync`). Intervalle : constante `_DIGEST_EVERY_N_SYNC`.

## Outil de debug — Analyse de la phase d'initialisation

- **`scripts/debug/init_report.py`** (`make init`, skill `/debug-run`) : rapport markdown
  ciblé sur le **démarrage** de la simulation, complémentaire de `run_report` (santé globale)
  et `llm_capacity` (débit LLM). Dérivé 100 % d'`app.log`, stdlib only, tolérant aux fichiers
  manquants. Contenu :
  - **Timeline des 5 étapes d'INITIALISATION** (SIM_START → INIT_DONE) avec la durée et la
    part de chacune ; repère l'étape dominante (quasi toujours le bootstrap `4/5`).
  - **Câblage & réchauffage des 3 caches persistants** (OTP, OSMnx, LLM sémantique) :
    activés ? chemins ? taux de hit atteint en fin d'init via la ligne de résumé combiné
    `[cache] OTP … · OSMnx … · LLM …` ; coût du chargement du modèle d'embedding.
  - **Bootstrap** : nombre d'agents pré-calculés, vagues d'anticipation, futurs déplacements
    pré-cachés, montée du taux de hit cache (cold → warm) et coût par type d'activité.
  - **Bugs d'init** avec section `🚨 ALARMES INIT` en tête : stalls de l'event loop
    (I/O synchrone du bootstrap → coupures WebSocket 1006), thrashing du cache métadonnées
    LTM (évictions + `gc.collect()` en boucle, `llm/longterm.py`), OD injoignables.
  - Exposé via `make init [RUN=… OUT=…]` et intégré à la skill `/debug-run`. Seuils
    d'alarme ajustables en tête de script.

## Cache LLM hybride et optimisation de la phase d'initialisation

L'init d'une population de 901 agents prenait ~19 min alors que les caches (OTP, OSMnx, LLM)
affichaient un taux de hit de ~100 % et que seuls 75 appels LLM réels avaient lieu. Le temps
était intégralement consommé par la machinerie entourant le cache, entièrement sérialisée :
un embedding `all-MiniLM-L6-v2` (~318 ms, sérialisé par `_embed_lock`) et une requête
ChromaDB de mémoire long terme étaient payés sur *chaque* décision, y compris les cache hits.

- **Cache sémantique LLM hybride.** Le lookup applique d'abord un filtre déterministe sur les
  conditions factuelles (agent, activité, catégorie de jour, tranche de 10 min, hash des
  options et de la météo), puis :
  - *LTM vide* (tout le bootstrap) : correspondance exacte par `scroll` clé-valeur, **sans
    embedding** (~0,1 ms contre ~324 ms). Sans souvenir, deux décisions prises dans les mêmes
    conditions sont identiques.
  - *LTM remplie* : recherche par similarité cosinus entre la mémoire courante de l'agent et
    celle qui a produit la décision stockée, avec rejet sous `cache.semantic_threshold`.
    L'agent tient donc compte de son vécu au lieu de rejouer indéfiniment sa première
    décision — ce que faisait l'ancienne clé, aveugle à la mémoire.
  Les deux familles de points sont étanches (`memory_empty` fait partie du filtre).
- **Le payload LLM (et sa requête ChromaDB) n'est plus construit sur le chemin nominal**
  quand la mémoire est vide : uniquement en cas de miss.
- **Nouveau champ de filtre `weekday`** : semaine et week-end ne partagent plus leurs décisions.
- **Fin du thrashing du cache métadonnées LTM** : `long_term_max_loaded_metadata` passe de 200
  à 5000 (nouveau réglage `agent.long_term_max_loaded_metadata`, jusqu'ici non câblé). En
  dessous du nombre d'agents, chaque décision provoquait une éviction. Le `gc.collect()` par
  éviction (~110 ms, exécuté dans l'event loop, ~2600 fois par init) est supprimé : il causait
  les stalls de la boucle asyncio (jusqu'à 148 s) et les coupures WebSocket 1006.

⚠️ Le filtre du cache gagne les champs `weekday` et `memory_empty` : les caches antérieurs ne
les portent pas et ne seront jamais retrouvés. Supprimer `data/llm_cache/` avant un run.

## Garde-fou TPM & débit des providers Groq

- **Réservation TPM glissante (60 s)** ajoutée au rate-limiter, en plus du RPM. `tpm_limit`
  devient un plafond dur appliqué avant chaque appel (réservation atomique RPM+TPM en un seul
  script Lua, restituée sur échec), et non plus un simple filtre de routage. Chaque provider
  expose `tpm_estimate_per_request = batch_max_agents × (assumed_prompt_tokens +
  assumed_output_tokens)`. Élimine le flot de **429** des providers dont le `rpm_limit`
  dépassait la capacité tokens réelle. Providers sans `tpm_limit` non bridés.
- **`groq_qwen` / `groq_llama31`** (free tier, TPM 6 000 → ~2 req/min) : `rpm_limit` ramené de
  60/30 à **2** et `weight` de 1.0 à **0.5**, alignés sur leur vraie capacité — ils causaient
  ~78 % des 429 pour une contribution marginale.

## Indicateur d'activités ratées faute de réponse LLM

- Nouveau compteur `agent_activity_decisions_total{outcome}` (issue de chaque activité
  planifiée : `llm`, `llm_fallback`, `single`, `no_solution`, `no_move`) émis au point de
  décision du contrôleur. Le **cockpit ③** (« Agents bloqués ») gagne une rangée : part et
  nombre d'activités dégradées faute de LLM (`llm_fallback` → index par défaut) et le débit
  fallback/min.
- Le **move-log** (`moves.csv`) porte désormais `ID Personne` et `ID Activité`. Le rapport de
  run (`run_report.py`, skill `/debug-run`) ajoute une section **« Couverture des activités
  par jour »** : les activités étant récurrentes et non datées, on vérifie que chaque activité
  d'un agent s'exécute chaque jour de sa plage — décomptant les activités *dégradées* (sans
  LLM) et *manquées* (aucune exécution ce jour-là), avec alarmes dédiées.
