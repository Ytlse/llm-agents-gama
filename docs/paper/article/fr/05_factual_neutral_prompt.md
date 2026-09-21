# 5. Protocole de calibration du choix modal

<!-- Dernière mise à jour : 2026-09-21 -->

**Document :** chapitre 5 de l'article AAMAS 2027 — le chapitre de **protocole** : il définit les conditions comparées, le chapitre 6 dit ce que la comparaison établit.
**Statut :** `brouillon v0.11` (21 septembre 2026) — relecture de l'auteur, huit points. Le § 5.2 sur le benchmark multi-modèles est dissous : la liste des modèles et son tableau remontent au chapeau, et les sections suivantes remontent d'un rang. La formulation mathématique du § 5.2.1 est ramenée à une phrase et une formule. Le § 5.2.2 dit la procédure réellement suivie — mutations successives d'un prompt unique, testées sur les cas censés basculer puis sur un rejeu apparié — et son illustration change : l'élasticité à la distance du champion `ref1` est retirée, ce diagnostic ne valant ni pour le prompt minimal (dont la part voiture va de 9,7 à 74,9 %) ni pour le prompt expert publié ; la dérive des retraités, mesurée et tracée, la remplace. Les garde-fous passent de quatre à trois et **cessent d'affirmer un vivier d'entraînement disjoint** : les écarts qui pilotent les mutations ont été lus sur la cohorte scellée, et les scores du chapitre 6 sont dits en échantillon. Le § 5.2.4 ajoute que le prompt expert vaut pour le modèle sur lequel il a été réglé. Le § 5.4 perd sa phrase d'ouverture justificative et le détail des moteurs de reconstitution. Aucun renvoi à un ticket ne subsiste dans le corps du texte. Troisième passe le même jour : les titres repassent sous la règle 1 du README — « Ce que la calibration cherche » devient « Perte par strate », « Comment le prompt est réglé » devient « Ingénierie de prompt », et « Les deux bouts de l'échelle » cède la place à « Planchers et références tabulaires ». Le § 5.2.4 est fondu dans le § 5.2.3. Le premier paragraphe du § 5.2.1 est réécrit par l'auteur, la glose de la formule et l'illustration des retraités partent en commentaire ou disparaissent.
**Statut antérieur :** `brouillon v0.10` (17 septembre 2026) — le titre devient descriptif : « Quatre façons de choisir, une seule information » annonçait une égalité d'information que le contrat du § 4.3 n'établit pas, celui-ci égalisant les 21 variables et non l'information dont chaque décideur dispose. Le § 5.3.5 publie le texte intégral du prompt expert de référence (`prompt_expert_05`), comme le § 5.1 publie celui du prompt minimal.
**Statut antérieur :** `brouillon v0.9` (16 septembre 2026) — reformulation selon les standards d'exigence AAMAS : formalisation mathématique de la calibration discrète sous contraintes au § 5.3, cadrage micro-comportemental au sein du système multi-agent, élimination des plaidoyers défensifs, et mise en conformité avec les règles de style (`make paper-style`).
**Statut antérieur :** `brouillon v0.8` (16 septembre 2026) — le fil rouge du chapitre est repris. Le chapeau pose la question du chapitre, jusqu'où un agent isolé de son environnement produit un comportement proche du réel, et dit que le protocole est une phase de calibration : régler le décideur sur le cas isolé et mesurable pour que la population reste représentative une fois replacée dans la simulation complète. Le § 5.1 dit ce que le prompt porte en propre face aux modèles de référence. Le § 5.2 est nouveau : le benchmark multi-modèles revient d'ameliorations.md, non plus en catalogue de fournisseurs mais comme raison de mesurer plusieurs modèles, avec sa note « à compléter ». Le prompt réglé devient le § 5.3, les bornes le § 5.4 et l'audit le § 5.5. Le § 5.4 cesse de chiffrer planchers et plafond : le § 4.4 publie les méthodes de référence et le § 6.1 le tableau complet, un chapitre de protocole définit les bornes et ne les mesure pas. Le vocabulaire des paliers sort du corps du texte au profit du nom des conditions.
**Place dans l'article :** section 5 du plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). Trame : [`../plan/PLAN.md`](../plan/PLAN.md). État d'avancement : [`../README.md`](../README.md).

---

Ce chapitre règle la politique locale de décision de l'agent avant son déploiement dans le simulateur. Le réglage porte sur un choix isolé : un déplacement précis, caractérisé par un profil sociologique, une offre multimodale calculée et des conditions météorologiques, sans historique dynamique de la journée écoulée. Les quatre paliers du § 1.3 y sont comparés à entrées égales, selon le protocole de comparaison du § 4.3.

Les deux conditions à modèle de langue sont mesurées sur `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` et `mistral-large-2512`, avec le même jeu de test, les mêmes contextes d'agents et la même randomisation de l'ordre des options.

<!-- sources: data/experiences/exp_{gemini-31-fl,gemini-35-fl,mistral-l-25}_{promin02,proexp05,proexp06,proexp08}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim, rejeu sur le jeu corrigé, exécutions des 2026-09-16 et 2026-09-17. Le décideur gemini-3.5-flash-lite sous prompt minimal, porté [xx] jusqu'au 2026-09-20, est mesuré : composite EMD–JSD 7,024, exécution 2026-09-16_19_05_45 ; le chapitre 6 le publie. Les décideurs agy-claude-o-5, agy-claude-o-4-6 et agy-gemini-38-f sont déclarés sans score. -->

## 5.1 Le prompt minimal

La condition de base évalue des modèles de fondation génériques, utilisés sur étagère sans ingénierie de prompt, face à un prompt minimal et circonstancié.

L'observation soumise au modèle est celle du § 3.3 : le profil sociologique, l'offre d'itinéraires viables avec le détail de leurs étapes, l'agenda des activités restantes et le contexte météorologique.

L'instruction système se limite à la définition de la tâche et au format d'émission de la décision :

> *Select the optimal travel mode taking the persona into account.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variante prompt_minimal_02 (82 mots, famille « minimale », audit de neutralité conforme du 2026-09-14) ; le schéma JSON attendu suit la consigne et est reproduit en annexe -->

Un cas d'inférence donne la structure du signal reçu par le modèle :

```
--- agent_id=1320713 | Destination: work | Departure: 08:16 ---
**Context:** Weather: 10°C, Clear/Sunny. Today 10°C to 22°C, sunrise 06:27,
sunset 21:15. No precipitation expected.
**Weather later:** afternoon 15°C, Clear/Sunny · evening 16°C, Clear/Sunny.
Frédéric-Adrien, 28, Full-Time Worker (household of 2, very low income).
Usual trip purposes: Work. Lives in: Toulouse

**Further trips planned today:**
    · 13:32 → other (≈12.4 km)
    · 16:27 → home (≈11.5 km)
    · 20:00 → leisure (≈15.1 km)

**Trip options** (5 options, indices 0 to 4):
- [0] foot,metro,foot: Travel time: 20 minutes, including 16 minutes of walking.
      Has a public transport pass.
    · Walk to 'Marengo-SNCF': 9 minutes.
    · Metro 'A' to 'Esquirol': 4 minutes.
    · Walk to 'work': 7 minutes.
- [1] foot: Estimated duration: 26 minutes. Distance: 2.0 km.
- [2] bicycle: Estimated duration: 11 minutes. Distance: 2.2 km.
- [3] foot: Travel time: 28 minutes, including 28 minutes of walking.
    · Walk to 'work': 28 minutes.
- [4] car: Estimated duration: 11 minutes. Distance: 3.0 km.
```

Réponse retournée par le modèle :

```json
[{"agent_id": "1320713",
  "probabilities": [
    {"index": 0, "mode": "foot,metro,foot", "probability": 20.0},
    {"index": 1, "mode": "foot",            "probability":  5.0},
    {"index": 2, "mode": "bicycle",         "probability": 50.0},
    {"index": 3, "mode": "foot",            "probability":  5.0},
    {"index": 4, "mode": "car",             "probability": 20.0}],
  "reason": "Frédéric-Adrien favors the fast 11-minute bicycle ride to save time
             on a tight schedule while keeping costs low, bypassing a slow walk."}]
```

<!-- source: bloc reçu et réponse — data/experiences/exp_gemini-35-fl_proexp04_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim/executions/2026-09-15_05_18_34/decisions.jsonl, person_id 1320713.
⚠ CAS À REPRENDRE AVANT PUBLICATION, et en entier. (1) Le départ de ce déplacement est résolu au 17 mars : c'est un des 866 cas que le ticket 088 a datés du lendemain, son offre d'itinéraires a donc été calculée pour le mauvais jour. (2) La réponse citée vient du décideur sous prompt expert, celui du palier 1 n'ayant pas de score sur la v6. Bloc reçu ET réponse sont à reprendre d'un décideur prompt_minimal_02 rejoué sur le jeu corrigé (ticket 088 § 3.4). -->

Le modèle reçoit cinq options pour un trajet de deux kilomètres, dont deux cheminements pédestres et une combinaison de marche et de métro. Sans directive sur la pénibilité de la marche, la valeur du temps ou l'effet de la météo, il répartit sa masse de probabilité entre les options. C'est cette distribution qui est scorée selon le protocole du § 4.3.

## 5.2 Le prompt expert

Le prompt minimal produit des écarts systématiques à l'enquête, et ces écarts se concentrent sur des strates identifiables. Le prompt système est réglé par itérations pour les réduire, sous la perte composite du § 4.2.

### 5.2.1 Perte par strate

Le prompt définit la politique locale de l'agent : pour chaque état perçu, il attribue une distribution de probabilités aux modes de transport disponibles. Pour une strate (tranche d'âge, motif, catégorie socio-professionnelle, lieu de résidence ou classe de distance), la part de chaque mode générée par le prompt correspond à la moyenne des probabilités qu'il associe aux déplacements de cette strate. L'enquête fournit la valeur de référence pour chaque strate. Calibrer, c'est trouver le texte qui minimise l'écart entre les probabilités produites par le prompt et ces valeurs de référence, strate par strate :

$$\min_p \sum_k w_k D_k(\hat{P}_k(p), P^*_k)$$

<!-- D_k : divergence de Jensen-Shannon sur les strates nominales, distance de transport optimal sur les strates ordonnées ; poids w_k du § 4.2. -->

### 5.2.2 Ingénierie de prompt

L'espace des textes est discret et non différentiable, et le score d'une variante se lit sur la distribution produite par une cohorte entière : dix prompts sur dix générations auprès de 800 personas demanderaient 80 000 inférences à une optimisation évolutionnaire (*EvoPrompt*, Guo et al., 2023). Le réglage procède par mutations successives d'un prompt unique, dans la lignée des approches réfléchies assistées par modèle (Shinn et al., 2023 ; Yuksekgonul et al., 2024).

Chaque itération part des écarts par strate produits par le prompt en service. Un modèle de langue lit ces écarts et les justifications que l'agent a écrites avec ses décisions, formule une hypothèse sur le mécanisme de raisonnement qui produit l'écart, et propose une mutation textuelle ciblée. La mutation est jouée d'abord sur une vingtaine de déplacements choisis pour être ceux que l'hypothèse dit devoir basculer, puis sur un échantillon stratifié plus large, rejoué à l'identique contre un bras témoin qui porte le prompt inchangé. Elle est retenue si le mode sur-représenté reflue sans qu'un autre écart se creuse ; sinon elle est rejetée, et le motif du rejet est consigné avec elle.

<!-- source: docs/traces/2026-09-08_16-05_prompt_expcha_derives_m5/README.md §§ 1 à 3 — run exp_gemini-35-fl_expcha_jtir_t0_nosim du 2026-09-08, 2 639 déplacements ; rejeu apparié de 200 décisions stratifiées en 25 lots de 8, six bras, texte utilisateur identique à l'octet (empreinte 6a4866b8673c) ; retraités L1 69,9 (témoin) → 62,9 (M1bis+M2+M3+M4+M5) ; M1 et M6 rejetées. Procédure : .agents/skills/optimiser-prompt-experience/SKILL.md, lignes 30 à 124 (deltas par strate, 20 cas cibles par mutation, critère de rétention). -->

### 5.2.3 Garde-fous d'admissibilité et prompt retenu

Trois contraintes encadrent le réglage.

1. **Aucun seuil chiffré.** Le prompt ne peut porter ni valeur numérique, ni borne kilométrique, ni objectif quantitatif (« privilégier la marche sous 1,5 km », « viser 55 % de choix automobile »). Un analyseur syntaxique élimine avant évaluation tout candidat qui en porte un. Le texte ne manipule que des notions d'arbitrage qualitatif : friction d'accès, fatigue physique cumulée, exposition aux intempéries, contraintes d'horaires.
2. **Aucune étiquette de l'enquête.** Le prompt ne nomme ni catégorie professionnelle, ni tranche d'âge, ni commune cible. Il formule ses heuristiques comme des principes transposables à un autre territoire.
3. **Mesure sur les distributions verbalisées.** Sur une cohorte de cette taille, un tirage stochastique disperse chaque part modale de $\pm 1,7$ point pour un même prompt. Le score de calibration est calculé sur les vecteurs de probabilités continus.

Les écarts qui pilotent les mutations ont été lus sur la cohorte scellée du chapitre 4 elle-même, pour l'essentiel des mutations retenues. Les scores du prompt expert rapportés au chapitre 6 sont donc des scores en échantillon, et non une performance de généralisation hors échantillon.

<!-- source: docs/tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md §§ 0.6 et 3.4 — prompt_expert_06/07/08 « édités au vu des scores de la cohorte scellée v5 » ; prompt_expert_05 = ablation de la clause anti-marche, mesurée sur la cohorte v5 le 2026-09-13 (5,79 contre 6,16) avant rétention, donc informée par la cohorte. Le seul prompt antérieur au premier run sur la cohorte, prompt_expert_04, a été supprimé du dépôt le 2026-09-17. Le vivier disjoint 50/20/30 (train 430, val 178, test 259, docs/arch/prompt_calibration.md § 3.2) appartient au module prompt_calibration et n'a pas servi aux variantes publiées. ±1,7 point : docs/arch/prompt_calibration.md ligne 75. -->

Un prompt expert vaut pour le modèle sur lequel il a été réglé. Les écarts par strate diffèrent d'un modèle à l'autre, et une mutation retenue sur l'un ne l'est pas de droit sur l'autre.

<!-- source: ticket 080 § 3.4, révisé le 2026-09-17 — prompt_expert_05 = palier 2, promu ce jour-là ; prompt_expert_04, qui portait ce statut, a été supprimé du dépôt à la demande de l'auteur et n'est plus servable ; prompt_expert_06/07/08 = ajustés au vu de la cohorte, publiés à part. Modèle de réglage : prompts.yaml, _provenance de prompt_expert_05, dérives mesurées sur exp_gemini-35-fl_expgem38v2_…_v5. -->

Seule l'instruction système distingue cette condition du prompt minimal. Le bloc de faits, la chaîne qui le produit et le schéma JSON attendu sont ceux du § 5.1. Le texte du prompt expert est le suivant :

> *Select the optimal travel mode taking the persona into account.*
>
> *Situational trade-off principles:*
>
> - *Chain friction: Reconstruct the real door-to-door duration (access walk, waiting, in-vehicle trip, egress). If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting.*
> - *Autonomy of older people: For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps to climb, standing while waiting with no bench).*
> - *Carrying logistics: Take into account the physical constraint of loads (shopping, heavy bags, carrier bags). Carrying loads on public transport is off-putting; the trade-off leans towards direct access with no interchange (an immediate neighbourhood walk, or the boot of a private vehicle).*
> - *Working people's life time: For a working person facing a tightly scheduled day, the time taken away from personal life has critical value. Faced with public transport links that significantly increase the duration or impose multiple interchanges, the traveller prefers the efficiency and schedule control of their available vehicle.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile through these principles.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variante prompt_expert_05 (277 mots, famille « experte », audit de neutralité conforme du 2026-09-14, sha256 du texte 5f55688f9cb3ba3e1e6c6f96549a339858ac72b110d9bdc7d14651c216b53ef4) ; le schéma JSON attendu suit la consigne et est reproduit en annexe -->

Les quatre principes s'ajoutent aux consignes de sortie du § 5.1, que la variante reprend à l'identique hormis le renvoi aux principes dans la première. Aucun ne porte de valeur numérique ni de cible de part modale, aucun ne nomme une catégorie de l'enquête.

## 5.3 Planchers et références tabulaires

Un écart de distribution se lit entre deux bornes : le niveau atteint sans connaissance comportementale, et celui qu'atteignent des modèles entraînés sur les réponses réelles.

Le plancher caractérise des décideurs ignorant toute information comportementale : le hasard uniforme, qui donne une probabilité égale à toutes les options calculées pour le déplacement ($1 / |\mathcal{O}_i|$) ; l'a priori empirique, qui met toute la probabilité sur le mode majoritaire du territoire, la voiture individuelle ; et l'heuristique de durée minimale, qui retient l'itinéraire le plus rapide sur les graphes de transport. Le plafond est la performance des quatre références tabulaires du § 4.4, lue axe par axe faute d'une méthode qui domine les trois.

Les scores des planchers et du plafond sont consolidés au tableau comparatif du chapitre 6. L'écart qui les sépare couvre un ordre de grandeur, les planchers affichant des divergences sept à quatorze fois plus élevées que les modèles supervisés.

<!-- repères d'exactitude sur la partition de test de l'enquête (13 045 déplacements, découpage par ménage, poids de redressement) : a priori « toujours la voiture » 57,1 %, logit multinomial 76,6 %, forêt aléatoire 77,6 %, régression logistique à noyau 78,4 %, gradient boosté 78,5 %. Sources : scripts/progedo_logit/{mode_choice_policy,klr_model,rf_mode_choice,mnl_model}_metrics.json, test.accuracy_weighted ; l'exactitude de l'a priori vaut la part observée de la voiture. Ces chiffres ne viennent PAS des scores.json de la campagne v6, qui ne portent aucune exactitude. Ils ne sont pas commensurables avec les composites : jeux différents, supports différents. -->

## 5.4 L'audit unitaire à parité de terrain

L'audit confronte le décideur, déplacement par déplacement, aux journées réellement décrites par les enquêtés : 2 930 personnes et 9 621 déplacements portant chacun le mode déclaré. L'offre d'itinéraires est reconstruite par les mêmes moteurs que la simulation, à partir des centroïdes des zones et de l'horaire déclaré, avec le bulletin météorologique du jour décrit.

Chaque décideur reçoit cette offre sous la contrainte de chaîne du § 3.5 : l'agent sous prompt minimal, l'agent sous prompt expert, les quatre modèles tabulaires supervisés (renormalisés sur l'offre selon la règle 3 du protocole) et le prior empirique. La chaîne rend l'offre dépendante du chemin, puisqu'un décideur qui a laissé la voiture au domicile ne se la voit plus proposer ensuite ; le nombre de déplacements dont le mode déclaré sort ainsi des options présentées est propre à chaque décideur. Cette confrontation unitaire permet de calculer les métriques de classification désagrégées annoncées au § 4.2 : exactitude globale pondérée, entropie croisée (LogLoss), matrices de confusion multi-classes, précision et rappel par mode de transport.

<!-- source: audit unitaire du 2026-09-19, neuf décideurs sur le jeu enquete_058_test_20260316 — hors options de 947 (majvoiture) à 1 428 (prompt minimal), 1 295 pour le prompt expert ; plafond partagé de 86 déplacements dont le jeu lui-même ne porte pas le mode déclaré ; déplacements internes à une zone fine écartés, un quart du total, leur distance n'étant pas mesurable entre deux centroïdes confondus ; l'agenda effectif de la journée vécue n'est connu que par les déplacements déclarés. Détail et seuils : docs/tickets/ticket_058_perimetre_et_methode_audit_unitaire.md -->

Cet audit évalue les modèles sur le substrat de données qui a servi à entraîner les références supervisées.

---

### Tickets associés à ce chapitre
- [Ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — Restructuration des chapitres 5 et 6, absorption du 4.5
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — Synthèse du benchmark multi-modèles et variabilité inter-graines
- [Ticket 004](../../../tickets/ticket_004_prompt_calibration_industrialisation.md) — Industrialisation de la calibration de prompt
- [Ticket 054](../../../tickets/ticket_054_sobriete_computationnelle_prompt_calibration.md) — Sobriété computationnelle de la calibration
- [Ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md) — Périmètre et méthode de l'audit unitaire (§ 5.4)
