# Ticket 024 — Diversité des choix et sensibilité au contexte : chiffrer les deux avant d'y toucher

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Nature du ticket** : *mesure*, pas correction. Rien n'est corrigé ici, ni en
> production ni dans l'instrument. Le ticket produit trois chiffres et les archive.
> Il emprunte au [protocole des paramètres exogènes](../arch/protocole-parametre-exogene.md)
> ses étapes 0 (jeton), 3 (A/B apparié), 4 (archivage) et 5 (porte de décision) — mais
> pas son étape 1 : il n'y a pas de paramètre à re-sourcer dans l'enquête.
>
> **Base de comparaison unique** : la dernière version de prompt **acceptée**
> (`expert_chaine`, la graine de la campagne `ref2`, prompt de production du jour).
> Tous les bras se lisent contre elle.

## La question

Deux affirmations circulent sur le modèle, et aucune n'est chiffrée :

- **D — le modèle manque de diversité.** Il pointerait vers une réponse figée, quasi
  unique. Depuis la bascule vers les **probabilités par option**
  (cf. [`llm-inference.md`](../arch/llm-inference.md)), on dispose enfin de la matière
  pour le vérifier : avant, le prompt demandait *un* choix, et la dispersion était
  inobservable par construction.
- **C — plus le contexte est riche, plus la sortie est juste.** Corollaire annoncé : le
  prompt a une influence, mais bornée ; ce qui compte davantage, c'est la quantité de
  réalité terrain servie au modèle.

Ce ticket les transforme en mesures opposables. Et il en ajoute une troisième, qui
n'était dans aucune des deux et qui décide pourtant du discours à tenir : **la
comparaison des amplitudes** prompt / contexte.

---

## Ce que la pré-mesure dit déjà, sans dépenser un appel LLM

**L'affirmation D est déjà à moitié établie, et personne ne l'a présentée comme telle.**
Les parts modales du champion de `ref1` par tranche de distance (jeu `screen`, relevé du
2026-08-17, cf. [`prompt_calibration/TODO.md`](../../prompt_calibration/TODO.md)) :

| tranche | n déc. | marche LLM / EMC² | voiture LLM / EMC² |
|---|---:|---|---|
| 0-1 km | 131 | 31,3 / 76,0 (**−44,7**) | 42,7 / 18,0 (+24,7) |
| 1-2 km | 118 | 15,3 / 40,0 (−24,7) | 46,6 / 43,0 (+3,6) |
| 2-5 km | 218 | 12,4 / 12,0 (+0,4) | 40,4 / 63,0 (−22,6) |
| 5-10 km | 169 | 9,5 / 1,0 (+8,5) | 42,6 / 70,0 (−27,4) |
| 10-20 km | 106 | 8,5 / 0,0 (+8,5) | 49,1 / 77,0 (**−27,9**) |

La part voiture produite est **plate** — 42,7 → 49,1 % — quand la réelle va de 18 % à
77 %. C'est la mesure directe d'une **absence de diversité inter-persona** : le modèle ne
répond pas à la distance. Et le déficit agrégé de marche (−14,5 pts) est la **somme**
d'un effondrement sur les courts trajets et d'un excédent sur les longs, qui se
compensent en partie. L'agrégat masque le défaut au lieu de le montrer.

**Conséquence pour ce ticket** : la moitié « inter-persona » de D est acquise et coûte
zéro appel. Ce qui reste à mesurer, c'est la moitié **intra-persona** — la distribution
servie pour un persona donné est-elle piquée ? — et c'est le bloc A.

---

## Bloc A — Diversité : trois bras, dont deux gratuits

Les évals stockées portent `decisions = (agent_id, mode, poids)`
([`store.py:80`](../../prompt_calibration/calibration/store.py), produites par
[`decisions_from_agents`](../../prompt_calibration/calibration/evaluation.py)). Tout ce
qui se déduit d'un vecteur de poids par persona est donc **relisible sans réinterroger le
modèle**, exactement comme `rescore --from-decisions` l'a fait pour `ref1`.

| Bras | Ce que c'est | Coût LLM |
|---|---|---|
| **A1** — pondéré | l'état actuel : chaque persona verse sa masse de probabilité | **0** — relecture du store |
| **A2** — vote majoritaire | `argmax` par persona, poids 1 sur le mode dominant | **0** — recalcul |
| **A3** — choix direct | le prompt redemande *un* mode, sans distribution | ~15 appels (1 bras) |

**A1 vs A2 est la mesure centrale, et elle est gratuite.** L'écart entre l'agrégat
pondéré et l'agrégat `argmax` **est** le coût du collapse : si le modèle était dispersé,
les deux agrégats seraient proches ; s'il est piqué, `argmax` amplifie le mode dominant.
Aucun appel, et le chiffre répond à D.

### Les métriques de dispersion à ajouter

Aucune n'existe dans [`metrics.py`](../../prompt_calibration/calibration/metrics.py), qui
ne connaît que l'écart à la référence (L1, EMD, JSD). Quatre à livrer, toutes calculables
depuis les décisions stockées :

1. **entropie normalisée par persona** `H(p_i) / log k_i`. ⚠ La normalisation par le
   nombre d'options **offertes** n'est pas cosmétique : un persona à 2 options a une
   entropie maximale de `log 2` et paraîtrait collapsé face à un persona à 6 options.
   Sans normalisation, la métrique mesurerait l'offre d'itinéraires, pas le modèle ;
2. **nombre effectif de modes** `exp(H)`, plus lisible qu'une entropie en rapport ;
3. **taux de réponses dégénérées** : part des personas dont `max p_i ≥ 0,90`, puis
   `≥ 0,99`. Deux seuils, parce que 0,99 distingue « décidé » de « déterministe » ;
4. **variance inter-persona des vecteurs de probabilité**. C'est le test propre du
   « figé sur une réponse unique » : si le modèle rend le même vecteur pour tout le
   monde, cette variance est nulle — **et l'agrégat peut malgré tout tomber juste sur la
   cible globale**. C'est le motif que le tableau de distances ci-dessus révèle par un
   autre chemin ; deux mesures indépendantes du même défaut valent mieux qu'une.

### ⚠ Le piège de A3, à ne pas manquer

`eval_temp` vaut **0,0** et il est **gelé** par le §3 du protocole
([`models.py:205`](../../prompt_calibration/calibration/models.py)). Un bras « choix
direct » à température nulle rend **une** réponse déterministe par persona : sa dispersion
intra-persona vaut **0 par construction de l'instrument**, pas par propriété du modèle.

C'est précisément le motif « l'absence de mesure produit le score parfait » que le dépôt
traque depuis le §2.1.1. Comparer la dispersion de A1 à celle de A3 dans ces conditions ne
mesurerait rien, et rien ne le signalerait. Deux conséquences, à tenir :

- **A1 vs A3 se lit au niveau agrégé uniquement** — parts modales, L1/EMD/JSD. C'est
  licite, et suffisant pour répondre à « l'ancien protocole était-il pire, et de
  combien ? » ;
- la dispersion de A3 exigerait **K répétitions par persona à température > 0** sur un
  sous-échantillon, ce qui **change l'instrument gelé**. Si elle est faite, elle est
  déclarée **hors instrument** et ne se compare à aucun composite de campagne. Elle n'est
  pas dans les lots ci-dessous.

---

## Bloc B — Sensibilité au contexte : une échelle d'ablation, pas un enrichissement

Le bloc A fait varier le **prompt** à jeu constant, comme
[`ab_chaine.py`](../../prompt_calibration/ab_chaine.py). Le bloc B fait l'inverse — varier
le **jeu** à prompt constant — comme
[`ab_terminal.py`](../../prompt_calibration/ab_terminal.py). Le prompt reste la **dernière
version acceptée** sur tous les paliers, sans exception : c'est la condition pour
attribuer l'écart au contexte.

**L'échelle se construit par retrait, pas par ajout.** Un enregistrement `v7` porte déjà
tout le contexte dans son champ `section` — et notamment la ligne `Mobilité :` qui
contient exactement les traits des tickets 015 à 018 (permis, disponibilité voiture,
abonnement TC, vélo personnel). Il n'y a donc **rien à produire** : il faut retirer, ce qui
est mécanique, vérifiable par diff, et ne demande aucune donnée nouvelle.

| Palier | Contexte servi | Retrait par rapport à `v7` |
|---|---|---|
| **L4** | `v7` tel quel | — (référence haute) |
| **L3** | sans la ligne `Mobilité :` | équipement du foyer |
| **L2** | L3 sans persona (âge, occupation, foyer, revenu) | identité sociale |
| **L1** | L2 sans météo (`context` + ligne « Météo plus tard ») | environnement |
| **L0** | L1 sans les sous-puces `·` des options | décomposition des étapes |

Ce que ça produit : une **courbe précision / quantité de contexte**, et surtout le palier
où elle **sature**. L'ordre du classement est prévisible ; ce qui a de la valeur est la
**pente** et le point de saturation.

### Le témoin nul est obligatoire ici aussi

Retirer du texte ne fait pas que retirer de l'information : ça raccourcit le contexte. Un
palier pourrait « améliorer » parce qu'il est plus court, pas parce qu'il est moins
informé. Le plancher de bruit est donc un palier **L4n** : même information que `v7`,
**reformulée et réordonnée** à longueur comparable. Son Δ est le bruit à la bonne masse.
Sans lui, la pente n'est pas opposable — c'est la leçon du témoin nul du
[ticket 023](ticket_023_fenetre_meteo_jeux_geles.md), où le Δ du traitement s'est révélé
quatre fois plus petit que celui d'un simple re-tirage.

---

## Le test qui décide du discours, et qui n'était dans aucune des deux affirmations

L'affirmation C se conclut par : *« le prompt joue, mais le contexte compte davantage »*.
C'est une **comparaison d'amplitudes**, et elle n'est produite par aucun bras ci-dessus
pris isolément :

| Amplitude | Valeur | Source |
|---|---|---|
| **prompt** — champion vs B0 non calibré | **−7,13** de composite, IC90 [−10,37 ; −4,35], n = 259 personas | T1 de `ref1`, amendement A5 |
| dont seeding (une seule réécriture LLM) | −5,35 sur `rank` | 29,82 → 24,47 |
| dont dix générations de recherche | −4,08 sur `rank` | 24,47 → 20,39 |
| **contexte** — `L4 − L0` | **à mesurer** | bloc B |

Si `L4 − L0` dépasse nettement 7,13, l'affirmation tient et elle est chiffrée. Sinon,
**c'est l'inverse qu'il faudra dire**. Cette comparaison est donc le livrable principal du
ticket, et elle passe avant le bloc A3.

⚠ **Les deux amplitudes ne sont pas mesurées sur le même jeu** (T1 sur `test`, le bloc B
sur `screen`/`val` — voir plus bas pourquoi `test` est fermé). La comparaison est donc
**indicative, pas un test statistique apparié**. À écrire à côté du chiffre, faute de quoi
un relecteur le fera.

---

## Les axes à instruire

| # | Axe | Question | Attendu |
|---|---|---|---|
| D1 | **Jeton d'exclusion** | Le protocole l'exige à l'étape 0. | **Levé le 2026-08-25** : `scripts/protocol_lock.py` existe (lot 1 du [ticket 023](ticket_023_fenetre_meteo_jeux_geles.md)), avec `make protocol-lock/unlock/status` et le garde `calibration/protocol_guard.py` que tous les `ab_*.py` appellent. ⚠ Le jeton est **local** : il ne bloque pas la campagne cloud |
| D2 | **Jeu de lecture** | Quels jeux ? | `screen` pour la pente (rapide, bon marché), `val` pour confirmer le palier retenu. **`test` est fermé** : son regard unique est consommé depuis l'amendement A5. Tous les chiffres de ce ticket sont **exploratoires**, jamais confirmatoires |
| D3 | **Nom des jeux** | Réutiliser `v7` avec un suffixe ? | **Non.** La clé d'éval porte `ds=<nom>`, pas une empreinte du contenu : un contenu qui change sous un nom stable fait servir une éval périmée en silence. Un nom neuf par palier. ⚠ Et le champ `version:` du manifeste doit porter **ce nom** : `v6` et `v7` portent tous deux `version: v5`, recopié de leur source — la filiation y est illisible |
| D4 | **Plancher de bruit** | Placebo ou témoin nul ? | **Témoin nul à pleine masse** (`L4n`, même information reformulée). Le canal placebo n'existe pas : l'ablation touche 100 % des enregistrements |
| D5 | **Périmètre du retrait** | Un palier ne retire-t-il **que** ce qu'il annonce ? | Diff strict, palier par palier, sous test. C'est le piège principal du protocole, qui a coûté la moitié d'un chiffre publié sur le temps terminal |
| D6 | **Effectif opposable** | Décisions ou personas ? | **Personas distincts.** Les déplacements d'un même agent partagent son profil ; annoncer les décisions surestimerait la précision. Les deux nombres sont affichés |
| D7 | **Injection du fait local** | Servir la part modale observée (« à Toulouse, X % des trajets < 1 km à pied ») corrige-t-il le biais culturel ? | **Témoin de plafond seulement, jamais un candidat de production** : c'est la cible dans le contexte. Hors des lots ci-dessous ; à instruire uniquement si la pente du bloc B sature avant d'atteindre la référence |
| D8 | **Où vivent les métriques** | Dans `metrics.py` ou dans un script d'analyse ? | Dans `metrics.py`, mais **hors du composite**. Ce sont des grandeurs de diagnostic : les faire entrer dans la loss changerait ce que la campagne optimise, ce qui n'est pas ce ticket |

---

## Lots

> **Lots 1, 2 et 3 livrés le 2026-08-25**, sans un seul appel LLM et sans jeton :
> métriques de dispersion (`calibration/metrics.py`, hors composite), tableau A1 vs A2 (`analyse_dispersion.py`) et les six paliers de l'échelle (`rewrite_context.py` → `ctxL0`…`ctxL4`, `ctxL4n`). Chiffres et trace : `docs/traces/2026-08-25_diversite_contexte/`, et §12 de [`prompt_calibration.md`](../arch/prompt_calibration.md).

1. **Lot 1 — Les métriques de dispersion (aucun appel LLM).** Les quatre grandeurs du
   bloc A dans `metrics.py`, hors composite, plus leur relecture sur les stores existants
   (`reference.db`, `calibration_cloud.db`). Tests : entropie normalisée sur un persona à
   2 options et un à 6, taux dégénéré aux deux seuils, variance nulle sur un jeu de
   vecteurs identiques, non-régression du composite.

2. **Lot 2 — A1 vs A2, le coût du collapse (aucun appel LLM).** Agrégation `argmax` par
   persona et tabulation en regard de l'agrégation pondérée, sur les mêmes évals. Les deux
   colonnes, plus l'écart par mode et par tranche de distance.

3. **Lot 3 — L'échelle de contexte.** `rewrite_context.py`, un palier = un retrait
   annoncé, `--dry-run` d'abord, diff strict par palier. Le témoin nul `L4n` est produit
   dans le même lot, pas plus tard : sans lui les autres paliers ne sont pas lisibles.

4. **Lot 4 — L'A/B du bloc B.** Jeton pris, modèle d'éval **épinglé**
   (`assert_pinned_eval_model`), prompt constant = dernière version acceptée, comparatif
   apparié, six colonnes (`L0`…`L4`, `L4n`) sur `screen`. Puis `val` sur le seul palier
   retenu.

5. **Lot 5 — A3, le choix direct.** Un bras, lu **au niveau agrégé uniquement**, avec la
   limite de `eval_temp = 0` écrite dans la sortie du script et pas seulement ici. Dernier
   servi : c'est le seul bras dont le résultat ne change aucune décision.

6. **Lot 6 — Archiver et publier.** `archive_ab.py --out ../docs/traces/<date>_diversite_contexte`,
   puis une ligne par mesure dans le journal `make avancement` — base de référence, base
   modifiée, modification, résultat, verdict. Les instantanés de quota du jeton entrent
   dans l'archive.

7. **Lot 7 — Porte de décision.** Trois issues possibles, et **le rejet s'archive autant
   que l'adoption** : (a) la pente est forte et sature tard → le prochain chantier est la
   donnée d'entrée, pas le prompt ; (b) la pente est forte et sature tôt → le palier de
   saturation devient la spécification du contexte de production ; (c) la pente est dans
   le bruit du témoin nul → **l'affirmation C est réfutée** et le discours change.

---

## Critères d'acceptation

- [ ] Les lots 1 et 2 rendent leurs chiffres **sans un seul appel LLM**, et la trace le
      démontre (aucune éval créée dans le store).
- [ ] L'entropie est **normalisée par le nombre d'options offertes**, et un test le vérifie
      sur un persona à 2 options et un persona à 6.
- [ ] Aucune des quatre métriques de dispersion n'entre dans le composite. Un test vérifie
      que le composite d'un nœud connu est **inchangé** après le lot 1.
- [ ] Aucun appel LLM n'est passé sans **jeton détenu**, et l'archive porte les instantanés
      de quota. Si le jeton n'existe pas encore, la procédure manuelle suivie est écrite
      dans la trace, avec ses deux relevés de quota.
- [ ] Le témoin nul `L4n` est mesuré et publié **dans le même tableau** que les paliers. Si
      un Δ de palier est du même ordre que le sien, le ticket le dit et refuse d'en tirer un
      effet.
- [ ] Chaque palier porte un **nom de jeu neuf**, et le champ `version:` de son manifeste
      porte ce nom — pas celui de sa source.
- [ ] Le diff de chaque palier ne touche **que** ce que le palier annonce retirer. Un test
      par palier.
- [ ] L'effectif opposable annoncé est le nombre de **personas distincts**, affiché à côté
      du nombre de décisions.
- [ ] La comparaison d'amplitudes prompt / contexte est publiée **avec** la mention qu'elle
      porte sur deux jeux différents et n'est pas un test apparié.
- [ ] Tous les chiffres sont étiquetés **exploratoires**. Aucun n'est lu sur `test`, et les
      scripts refusent ce jeu.
- [ ] La trace est committée dans `docs/traces/` et chaque mesure a sa ligne dans
      `make avancement`, y compris en cas de rejet.

## Hors périmètre

- **La mémoire et la réaction aux perturbations.** Effet d'historique, comportement face à
  une perturbation : c'est un chantier distinct, et il ouvre sur un autre ticket. Rien ici
  ne l'instruit.
- **La dispersion intra-persona de A3.** Elle exigerait K tirages à température > 0, donc
  une modification de l'instrument gelé. Hors lots ; si elle est faite un jour, c'est hors
  instrument et sans comparaison de composite.
- **L'injection du fait local (axe D7).** Témoin de plafond, conditionné au résultat du
  bloc B. Jamais un candidat de production.
- **Faire entrer la dispersion dans la loss.** Optimiser le prompt sur une entropie cible
  changerait ce que la campagne cherche. C'est une décision d'architecture, pas un
  sous-produit d'une mesure.
- **Corriger quoi que ce soit.** Ce ticket ne modifie ni le prompt de production, ni les
  jeux de production, ni un paramètre. Il mesure, il archive, il ouvre une porte.

## Ce qu'il faut savoir avant de commencer

- **Le jeton d'exclusion est retiré** *(mis à jour le 2026-08-26 — retrait demandé, cf.
  commit « Retrait du jeton d'exclusion : plus de verrou, une vigilance manuelle »)*.
  `scripts/protocol_lock.py`, `make protocol-lock/unlock/status` et le garde
  `calibration/protocol_guard.py` sont partis ; il n'y a plus de verrou à prendre pour les
  lots 4 et 5. Ce qui reste exigé — deux bras évalués par le même juge, aucun run ni
  service consommateur concurrent, campagne cloud en pause (`CLOUD_PAUSED=1`) — se vérifie
  désormais à la main avant de mesurer, sans preuve automatique : une trace ne peut plus
  produire qu'une affirmation, pas un jeton committé. Les mesures publiées avant ce retrait
  gardent leur jeton dans leur trace archivée (ex. ticket 023, lot 1).
- **Le juge n'est plus prescrit par le §3** *(amendement A11, 2026-08-25)*. Le protocole ne
  nomme aucun modèle : il exige la **constance du juge à l'intérieur d'une comparaison**.
  Les six colonnes du bloc B doivent donc partager un juge, et ce juge doit être cité à côté
  du chiffre — mais lequel est un arbitrage d'exploitation, pas de protocole.
- **`screen` ne se lit plus seul** *(leçon du ticket 023)*. 121 personas, plancher de bruit
  six fois plus étroit que `val`, et **deux** signaux fabriqués qu'il n'a pas confirmés. La
  pente du bloc B se lit sur `screen` **et** `val`, pas sur `screen` puis `val` au seul
  palier retenu.
- **La moitié du bloc A est déjà acquise et coûte zéro.** Commencer par les lots 1 et 2
  donne des chiffres immédiatement, sans jeton, sans quota, sans attente. Ne pas
  commencer par l'A/B.
- **Le regard unique sur `test` est consommé** (amendement A5, et la première lecture avait
  d'ailleurs rendu un chiffre faux, −3,41 au lieu de −7,13, faute de dimensions
  mesurables). Aucun chiffre de ce ticket n'est confirmatoire. Le dire en présentation
  n'est pas une réserve à cacher, c'est ce qui rend le reste crédible.
- **L'issue « pas d'effet » est une issue normale.** Si la pente du bloc B est dans le
  bruit du témoin nul, l'affirmation C tombe — et c'est un résultat, à archiver comme les
  autres. Ne pas dimensionner l'effort sur l'espoir d'une belle courbe.
- **Modèle d'éval épinglé et stable sur toute la branche.** Un alias flottant mélangerait
  deux modèles sous une même clé de cache ; changer de modèle en cours de branche détruit
  le cache d'éval déjà payé.
- **`prompt_calibration` est un dépôt git autonome.** Tout garde-fou ou lecture partagée
  doit fonctionner sans le dépôt principal sur le `sys.path` — comme `weather.py` recopie
  la mise en forme météo pour cette raison, avec un test qui compare les deux.

## Sources

- [`docs/arch/protocole-parametre-exogene.md`](../arch/protocole-parametre-exogene.md) —
  les étapes empruntées (0, 3, 4, 5) et les deux pièges documentés.
- [`docs/arch/prompt_calibration.md`](../arch/prompt_calibration.md) — §10 (A/B d'un
  fragment de prompt), §11 (A/B d'un jeu réécrit), et §2.1.1 sur la mesurabilité.
- [`prompt_calibration/PROTOCOLE.md`](../../prompt_calibration/PROTOCOLE.md) — §1 (la
  question de recherche : une dispersion, pas une décision), §3/§4 (instrument et métrique
  gelés), §8 (regard unique), amendements A5 et A7.
- [`prompt_calibration/TODO.md`](../../prompt_calibration/TODO.md) — le tableau
  d'élasticité à la distance et la décomposition seeding / recherche.
- [`prompt_calibration/calibration/evaluation.py`](../../prompt_calibration/calibration/evaluation.py)
  — `decisions_from_agents`, et pourquoi la mesure est pondérée plutôt que tirée.
- [`prompt_calibration/calibration/store.py`](../../prompt_calibration/calibration/store.py)
  — la table `evals` et son champ `decisions`, ce qui rend les lots 1 et 2 gratuits.
- [`prompt_calibration/ab_terminal.py`](../../prompt_calibration/ab_terminal.py) et
  [`rewrite_terminal_time.py`](../../prompt_calibration/rewrite_terminal_time.py) — le
  patron à reprendre pour `rewrite_context.py`, y compris son piège de troncature de
  décimale.
- [ticket 023](ticket_023_fenetre_meteo_jeux_geles.md) — le jeton d'exclusion (lot 1, non
  livré) et la démonstration de la nécessité d'un témoin nul.
