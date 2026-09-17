# État d'avancement de la rédaction française

<!-- Dernière mise à jour : 2026-09-15 -->

**Objet :** où en est chaque document de ce dossier, document par document. Ce fichier est
tenu **à la main** par l'auteur : rien ne le régénère, et une ligne qui ne bouge pas quand le
texte bouge est pire que pas de ligne du tout.

**Ce qu'il ne dit pas :** la parité entre les trois arbres (`fr/`, `en/`, `overleaf/`) et les
numéros de version par langue restent dans [`../README.md`](../README.md), vérifiés par
`make paper-parite`. Ici, seul l'avancement du **français** — c'est lui qui se rédige en
premier (décision de l'auteur du 11 septembre 2026).

**Le chapitrage de référence** est celui de [`../plan/PLAN.md`](../plan/PLAN.md), lui-même
dérivé de la section 1.4 du chapitre 1. Les écarts entre ce qui est prévu et ce qui est
réellement dans le fichier sont relevés fiche par fiche, plus bas.

## Légende

| Statut | Sens |
|---|---|
| ⬜ pas commencé | le fichier n'existe pas, ou ne contient que son en-tête |
| 🟠 brouillon hérité | texte extrait du manuscrit `v1.6` (3 septembre 2026), non retravaillé depuis |
| 🧭 trame | corps vidé volontairement : chaque section dit ce qu'elle doit établir et ce qu'il lui faut |
| 🟡 en cours d'écriture | réécriture engagée, chapitre incomplet |
| 🟢 première version écrite | texte neuf et complet, jamais relu |
| 🔵 relu | passé en relecture ; les points encore ouverts sont listés |
| ✅ arrêté | fond figé, anglais et LaTeX à parité |

---

## Vue d'ensemble

| # | Fichier | Statut | Overleaf | Version | Ce qui reste |
|---|---|---|---|---|---|
| 0 | [`00_abstract.md`](00_abstract.md) | 🔵 relu | 🟢 alignée | `v0.5` | 8 emplacements chiffrés ; les deux modes biaisés ne sont plus nommés |
| 1 | [`01_introduction.md`](01_introduction.md) | 🔵 relu | 🟢 alignée |  `v0.21` | 1 remarque de relecture encore ouverte (point 4.13) |
| 2 | [`02_related_work.md`](02_related_work.md) | 🔵 relu | 🟢 alignée |  `v0.17` | rien d'ouvert à ce jour |
| 3 | [`03_architecture.md`](03_architecture.md) | 🟢 première version | 🟢 alignée | `brouillon v0.5` | quadruplet et tirage posés, espace d'action en clair ; § 3.4 écrit sur l'état visé du ticket 071 |
| 4 | [`04_metrics_and_substrate.md`](04_metrics_and_substrate.md) | 🟢 première version | ⬜ Vide | `brouillon v0.9` | socle et cohorte chiffrés sur la v6 ; plus aucun emplacement `[xx]` ; lecture des chiffres à relire |
| 5 | [`05_factual_neutral_prompt.md`](05_factual_neutral_prompt.md) | 🟢 première version | ⬜ Vide | `brouillon v0.8` | chapitre de **protocole** ; quatre sections rédigées, fusion du 4.5 faite, planchers chiffrés ; réponse du bras palier 1 à reprendre, audit du § 5.4 à jouer |
| 6 | [`06_results.md`](06_results.md) | 🟠 brouillon |  ⬜ Vide |`trame v0.1` | chapitre de **résultats**, à l'arrêt : idée directrice et titre en décision ([ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md)) |
| 7 | [`07_untabulated_regimes.md`](07_untabulated_regimes.md) | 🟠 brouillon hérité | ⬜ Vide | `brouillon v0` | campagnes non jouées, numérotation périmée |
| 8 | [`08_limits_and_hybrid.md`](08_limits_and_hybrid.md) | 🟠 brouillon hérité | ⬜ Vide | `brouillon v0` | la limite de l'itinéraire mixte reste à écrire |
| 9 | [`09_conclusion.md`](09_conclusion.md) | 🟠 brouillon hérité | ⬜ Vide | `brouillon v0` | aucune des trois sous-sections prévues |
| 99 | [`99_annexes.md`](99_annexes.md) | 🟠 brouillon hérité | ⬜ Vide | `brouillon v0` | annexes A à D réduites à une ou deux phrases |

**Lecture d'ensemble :** trois chapitres relus (0, 1, 2), trois écrits neufs et jamais relus
(3, 4, 5), un en trame (6, à l'arrêt depuis la restructuration du 15 septembre 2026), et quatre
qui sont encore l'extrait du manuscrit (7, 8, 9, 99).

**Le point dur, au 15 septembre 2026 :** les scores recalculés depuis le dépôt ont paru un
moment contredire l'hypothèse **H0 de non-atteinte** que le chapitre 6 devait établir. Cette
contradiction venait d'un journal de mouvements tronqué (ticket 081) ; une fois celui-ci
reconstitué, le prompt calibré reste derrière les modèles tabulaires sur les trois lectures, et
H0 n'est pas réfutée. L'idée directrice du chapitre,
son titre, et la répercussion sur le résumé, le § 1.3 et le chapitre 9 sont en décision au
[ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
Rien ne se rédige dans le 6 avant que trois verrous soient levés : dispersion non mesurée
(ticket 073), lecture de référence non arrêtée (ticket 046), deux décideurs à modèle de langue seulement scorés sur
v6 et sans réplicat (ticket 074).
Les cinq derniers partagent la même dette : vocabulaire « Tier 1 / 2 / 3 » à remplacer par
*exploratory / robust / transferable*, chiffres à recouper depuis le dépôt, renvois de section
à refaire, et une numérotation interne qui est encore celle du manuscrit.

---

## Fiches par document

### 0 — `00_abstract.md` · Résumé

**Statut :** 🔵 relu · `v0.5` (13 septembre 2026) · 834 mots de fichier, 241 mots de résumé
**Sections prévues :** texte d'un seul tenant, quatre paragraphes (cadrage, dispositif, résultats, portée)
**Présent :** les quatre paragraphes.
**Reste à faire :** 8 emplacements `[xx]` — erreurs L1 des deux conditions LLM, du logit et du
gradient boosté. Point ouvert consigné en en-tête : la v0.2 annonçait une sur-attraction du **vélo**,
le run du 8 septembre 2026 mesure celle des **transports en commun** ; les deux modes biaisés
ne sont plus nommés en attendant que les résultats se stabilisent.
**Relecture :** [`../relecture/00_abstract.md`](../relecture/00_abstract.md) — comparaison v0.1 / v0.2 / v0.3, close.
**Mes notes :**

### 1 — `01_introduction.md` · Introduction

**Statut :** 🔵 relu · `v0.22` (16 septembre 2026) · 4 758 mots
**Sections prévues :** 1.1 contexte · 1.2 plausibilité individuelle et agrégat · 1.3 contributions et hypothèses · 1.4 organisation
**Présent :** les quatre, dans l'ordre.
**Reste à faire :** un point de relecture encore marqué ⏳ — 4.13, « two hypotheses » alors
qu'une seule est préenregistrée. Le substrat est passé à la cohorte scellée **v6** en `v0.21`.
**À vérifier :** le tableau d'avancement de [`../README.md`](../README.md) annonce encore `v0.19`.
**Relecture :** [`../relecture/01_introduction.md`](../relecture/01_introduction.md) — porte aussi le chapitre 2.
**Mes notes :**

### 2 — `02_related_work.md` · Travaux connexes

**Statut :** 🔵 relu · `v0.17` (10 septembre 2026) · 2 418 mots
**Sections prévues :** 2.1 utilité aléatoire et rationalité limitée · 2.2 agents génératifs en mobilité · 2.3 alignement distributionnel
**Présent :** les trois.
**Reste à faire :** rien d'identifié. Les citations ont été vérifiées sur les notices arXiv le
10 septembre 2026 ; le suivi par référence est dans [`../CITATIONS.md`](../CITATIONS.md).
**Mes notes :**

### 3 — `03_architecture.md` · Le dispositif : décider dans une ville contrainte

**Statut :** 🟢 première version écrite · `brouillon v0.5` (15 septembre 2026)
**Sections prévues :** 3.1 vue d'ensemble · 3.2 le terrain · 3.3 le point de décision · 3.4 la mémoire · 3.5 modélisation par chaînes de déplacements
**Présent :** les cinq, plus la figure 1 (`images/architecture_GAMA_Agents.jpg`). Texte neuf, écrit
directement en français, et non un extrait du manuscrit.
**Reste à faire :** le § 3.4 est écrit sur l'**état visé** du ticket 071 — à recouper sur le code
quand les lots seront livrés. Le § 3.3 (« les deux voient la même chose ») attend l'arbitrage du
ticket 046. Deux renvois au « chapitre 4 » pour le plancher et le plafond deviendront « chapitre 5 »
si le chapitrage du ticket 080 est retenu.
**Tickets :** 050 formalisation mathématique (*appliqué en v0.5 ; espace d'action laissé en clair, décision du 15/09*) · 051 refonte de l'architecture mémoire (*en cours*) · 070 accidents et retard subi (*anticipé*) · 071 évolution de la mémoire (*anticipé*) · 046 asymétrie du contrat (*dépendance notée*)
**Mes notes :**

### 4 — `04_metrics_and_substrate.md` · Métriques et socle d'évaluation

**Statut :** 🟢 première version écrite · `brouillon v0.9` (15 septembre 2026)
**Sections prévues :** 4.1 deux échelles · 4.2 les trois règles du contrat · 4.3 socle de référence · 4.4 cohorte scellée
**Présent :** les quatre. Texte neuf. Le périmètre de mesure (ancienne 4.3) et le dimensionnement
de l'échantillon ont quitté le chapitre. Le socle (4.3) et le contrôle démographique (4.4) sont
chiffrés sur la cohorte v6 et ses exécutions du 14–15 septembre 2026.
**Reste à faire :** relecture de l'auteur sur les paragraphes de lecture du tableau 4.3 ; la
note « point à travailler » de la règle 1 attend le ticket 046.
**Tickets :** 043 régression logistique à noyau · 045 substrat unique · 046 asymétrie informationnelle · 047 offre à mode unique · 052 cohorte scellée · 053 accès aux données
**Mes notes :**

### — `04.5_prompt_calibration.md` · Calibration du prompt *(fusionné et archivé)*

**Statut :** ✅ fusionné au § 5.2 le 15 septembre 2026, puis **archivé** sous
[`../../archive/04.5_prompt_calibration_v0.1.md`](../../archive/04.5_prompt_calibration_v0.1.md) ·
`brouillon v0.1` · 1 994 mots. Le numéro intercalaire `4.5` **a disparu de l'article**.
**Ce qui n'a pas été repris :** la section 4.5.2 (goulet computationnel de la recherche
génétique), réduite à un paragraphe en 5.2 — écartée sur son **coût en tokens**, pas par
principe — et sa perspective, qui part au chapitre 8.
**Ce qui a été corrigé dans la fusion :** la règle 2 affirmait qu'« aucun persona du jeu de test
n'est vu au cours de la calibration ». C'est vrai de la variante qui porte le palier 2, faux des
variantes ajustées au vu de la cohorte ; le § 5.2 les sépare et les publie sous deux statuts
distincts (ticket 080 § 3.4).
**Tickets :** 080 restructuration · 004 industrialisation · 054 sobriété computationnelle
**Mes notes :**

### 5 — `05_factual_neutral_prompt.md` · Quatre façons de choisir, une seule information

**Statut :** 🟢 première version écrite · `brouillon v0.8` (16 septembre 2026) · passe `make paper-style` et les règles d'écriture du README
**Rôle :** le chapitre de **protocole** — il définit ce que l'on compare ; le 6 dit ce que la
comparaison établit.
**Fil rouge (repris le 16 septembre) :** le chapitre est une **phase de calibration**. Jusqu'où un
agent isolé de son environnement produit-il un comportement proche du réel ; on répond par étapes,
en donnant de plus en plus d'indications au modèle, et on compare aux méthodes classiques sur le
même périmètre. Le but est un décideur qui reste représentatif une fois la population replacée
dans la simulation complète.
**Sections :** chapeau · 5.1 le prompt factuel neutre *(avec un exemple complet)* · 5.2 le
benchmark multi-modèles *(nouveau, à compléter)* · 5.3 le prompt réglé *(fusion du `04.5`)* ·
5.4 planchers et plafond *(définitions seules, plus de chiffres)* · 5.5 l'audit à parité de
terrain.
**Vocabulaire :** « palier 1 / palier 2 » sort du corps du texte au profit du nom des conditions ;
« palier » ne subsiste qu'une fois, dans la carte du § 5.4, pour le lien avec le § 1.3.
**Sorti du corps du texte le 16 septembre :** la note de restructuration et le benchmark
multi-modèles conservé partent dans [`../ameliorations.md`](../ameliorations.md) — ils décrivaient
la fabrication et non la mesure. La destination du benchmark reste à trancher (annexe ou § 6.1).
**Chiffré depuis le dépôt :** les trois planchers sur la cohorte v6 (composite EMD–JSD et L1
global, sous contrainte de chaîne) et l'exactitude des quatre familles tabulaires sur la partition de test de
l'enquête.
**Sorti du chapitre :** le protocole de variabilité devient le § 6.3 — la dispersion est un
résultat, pas un point de méthode. Le benchmark multi-modèles quitte le corps du chapitre : à
huit pages, l'inventaire des fournisseurs est un catalogue ; destination à trancher (annexe ou
tableau en 6.1), texte conservé en bas du fichier en attendant.
**Chiffré depuis le dépôt :** les trois planchers et le plafond du § 5.3 sont lus sur le **jeu
corrigé du ticket 088** (exécutions du 16 septembre, suffixe `_c`), sur les trois axes du § 4.4 et
sous la seule lecture en chaîne.
**Reste à faire :** (1) l'exemple du § 5.1 porte un déplacement daté du 17 mars, donc un des 866
cas défectueux du ticket 088 : bloc reçu **et** réponse sont à reprendre d'un décideur `prompt_minimal_02`
rejoué sur le jeu corrigé ; (2) l'audit du § 5.4 est décrit mais pas encore joué (ticket 058) ;
(3) le coût de la calibration et le nombre d'itérations de la boucle restent à chiffrer
(ticket 054) ; (4) le renommage des paliers en A (minimal) et B (expert), 10 occurrences ici,
attend la passe d'ensemble.
**Hors chapitre, à porter ailleurs :** le § 1.4 de l'introduction annonce encore l'ancien
découpage — il donne au chapitre 5 la variabilité inter-graines, partie au § 6.3, et au chapitre 6
l'ablation, la condition calibrée et les références tabulaires, qui sont ici. Correction à faire
dans les trois arbres, le chapitre 1 étant relu en `v0.22`.
**Hors chapitre, décidé le 15 septembre :** la fenêtre de tirage de la météo — l'année entière
quand l'enquête couvre 20/09 → 18/02 — ne figure pas dans le chapitre 5. Le constat et ses
mesures vivent au ticket 023 ; si le point entre dans l'article, ce sera au chapitre 8.
**Tickets :** 088 jeu corrigé · 080 restructuration · 058 audit unitaire · 055 benchmark et
variabilité · 054 coût de la calibration · 083 signature IA
**Mes notes :**

### 6 — `06_results.md` · *titre à arrêter* — ce que la comparaison établit

**Statut :** 🟢 rédigé · `brouillon v0.4` (17 septembre 2026) · passe `make paper-style`
**Rôle :** le chapitre de **résultats**.
**Ce qu'il établit :** chaque résultat porte sur un couple, un modèle de langue et une consigne.
L'ingénierie de prompt rapproche les modèles de la distribution d'enquête, le porteur pèse autant
que la consigne, un seul des trois couples vient à portée du plafond tabulaire, et cette
proximité des marges recouvre un désaccord décision par décision. Quatre figures en anglais,
régénérées par `scripts/analysis/plot_chapitre6.py` ; le détail des résultats vit à l'annexe H.
**Sections :** 6.1 treize décideurs sur la même échelle · 6.2 ce que l'ingénierie de prompt
déplace · 6.3 le détail des résultats agrégés, sur Gemini 3.5 · 6.4 décider pareil, décider
autrement · 6.5 variation de cohorte et dispersion entre graines. Le détail des résultats vit à
l'annexe H du chapitre 99.
**Ce qui reste ouvert :** la dispersion inter-graines, écrite comme acquise et marquée **TBC**
(ticket 073, axe 1) · l'exactitude unitaire de l'agent, deux `[xx]` au § 6.4 (ticket 058) · la
lecture de référence non arrêtée (chapitre 4 § 4.3, ticket 046). Les treize décideurs sont
mesurés sur le jeu corrigé du ticket 088 depuis le 2026-09-17.
**En décision :** l'idée directrice et le titre — trois options posées au
[ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
**Tickets :** 080 *(bloquant)* · 073 · 056 · 057 · 058
**Mes notes :**

### 7 — `07_untabulated_regimes.md` · Régimes non tabulés : hystérésis et presse locale

**Statut :** 🟠 brouillon hérité · `brouillon v0` · 1 220 mots
**Sections prévues :** 7.1 hystérésis sur cinq jours · 7.2 cinq événements de presse locale · 7.3 prédictions préenregistrées
**Présent :** 5.1 · 5.2 · 5.3 — même contenu, numérotation du manuscrit.
**Reste à faire :** les deux campagnes ne sont pas jouées ; les chiffres cités viennent du
manuscrit et n'ont pas été recoupés ; vocabulaire « Tier 1 / 2 / 3 » à reprendre.
**Tickets :** 041 hystérésis longitudinale · 059 presse locale et prédictions préenregistrées (*à faire*) · 063 campagne hystérésis · 064 campagne presse locale
**Mes notes :**

### 8 — `08_limits_and_hybrid.md` · Limites et implications hybrides

**Statut :** 🟠 brouillon hérité · `brouillon v0` · 795 mots
**Sections prévues :** 8.1 limites · 8.2 la cascade hybride en perspective · 8.3 cadre comparatif · 8.4 échelle du foyer et chaînes de véhicules
**Présent :** 6.1 · 6.2 · 6.3 — numérotation du manuscrit ; la section 8.1 « limites » n'existe
pas en propre, alors que c'est la première annoncée.
**Reste à faire :** le bloc « À écrire » de l'en-tête — la **limite de l'itinéraire mixte**
(OTP est interrogé mode par mode, aucun trajet combiné n'est proposé à l'agent), deux
paragraphes qui doivent porter l'amplitude *et* le sens du biais.
**À trancher :** le ticket 049, qui porte cette limite, est marqué **terminé** dans
`tickets_status.yaml`, alors que le texte ne l'a pas encore intégrée.
**Tickets :** 049 itinéraire mixte (*terminé — à vérifier*) · 060 formalisation de l'architecture hybride (*à faire*)
**Mes notes :**

### 9 — `09_conclusion.md` · Conclusion

**Statut :** 🟠 brouillon hérité · `brouillon v0` · 453 mots — le plus court du dossier
**Sections prévues :** 9.1 ce que l'évaluation établit en régime nominal · 9.2 domaine de pertinence des agents génératifs · 9.3 ce que l'hybridation résout et laisse ouvert
**Présent :** aucune des trois. Le fichier est une liste de quatre enseignements numérotés,
héritée du manuscrit, avec des chiffres non recoupés (93,4 % d'accuracy, composite 9,28 contre 7,40).
**Reste à faire :** tout, une fois les chapitres 6 et 7 arrêtés — une conclusion s'écrit en dernier.
**Tickets :** 061 finalisation du chapitre 9 (*à faire*)
**Mes notes :**

### 99 — `99_annexes.md` · Annexes techniques

**Statut :** 🟠 brouillon hérité · `brouillon v0` · 1 633 mots
**Annexes prévues :** A quotas API et plateforme · B script d'évaluation sur enquête · C inférence locale Qwen-32B · D bilan de la calibration et justification du pivot · E dictionnaire des 21 variables · F journal des corrections méthodologiques · G source des données d'enquête

| Annexe | État |
|---|---|
| A — Quotas API & plateforme | deux phrases ; chiffres de gateway à réactualiser |
| B — `eval_llm_on_survey.py` | une phrase ; le script n'est pas décrit |
| C — Inférence locale Qwen-32B | une phrase |
| D — Bilan de la calibration | une phrase ; c'est pourtant la justification du pivot hybride |
| E — Dictionnaire des 21 variables | rédigée, c'est la plus complète — elle adosse le contrat de la section 4.3 |
| F — Journal des corrections v1.4 → v1.6 | rédigée ; à prolonger au-delà de v1.6 |
| G — Source des données, citation et engagements | rédigée ; convention `lil-1750` |

**Reste à faire :** A à D sont des titres avec une phrase dessous, pas des annexes. Décider
lesquelles survivent à la contrainte de pages avant de les étoffer.
**Tickets :** 053 accès aux données et reproductibilité · 062 revue et alignement des annexes A à G (*à faire*)
**Mes notes :**

---

## Voir aussi

- [`../README.md`](../README.md) — versions, parité des trois arbres, règle de mise à jour
- [`../plan/PLAN.md`](../plan/PLAN.md) — le chapitrage de référence
- [`../relecture/`](../relecture/) — relecture section par section (chapitres 0 et 1 à ce jour)
- [`../actions.md`](../actions.md) — actions de rédaction, risques relecteurs, objections
- [`../ameliorations.md`](../ameliorations.md) — points retirés du texte, à consolider ailleurs
