# Ticket 103 — Le carré Jev × Gemini hors échantillon, et trois graines par décideur clé

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-22, à la demande de l'auteur, après la relecture sévère de l'article
> menée le même jour (`docs/paper/article-court/`).
>
> **Objet.** Deux mesures manquent pour que la thèse de l'article court tienne devant un
> relecteur, et toutes deux se règlent en temps machine. **(1)** Le résultat pivot, le classifieur
> à sortie typée `jev-1.13.0` dans la bande des références tabulaires à 3,65 de composite,
> repose sur un prompt réglé **en échantillon** (`prompt_expert_32`, muté sur les écarts par
> strate de la cohorte qui le note), comparé à un prompt gemini réglé **hors échantillon**
> (`prompt_expert_05`, population de calibration séparée, transféré tel quel). L'asymétrie
> favorise Jev, donc la thèse. **(2)** Le § 6.5 affirme que la dispersion inter-graines laisse
> les écarts en place, et son commentaire dit *do not publish this paragraph without that
> replay*. Trois graines existent pour un seul décideur.
>
> **Ce ticket bloque la rédaction du plan `docs/paper/article-court/PLAN.md` en version
> définitive.** Le plan est écrit sous l'hypothèse que les deux points sont réglés ; ses § 5.3
> et § 7 changent de portée selon l'issue (voir § 5 ci-dessous).

> **⚠ 2026-09-24 — rôle des cohortes inversé, décision de l'auteur.** La cohorte
> `population_1000_AAMAS_v6` (jeu `…_20260316_EN_c`) reste la cohorte **scellée** : on y mesure,
> on n'y règle rien. La cohorte `population_1000_AAMAS_v6_c2` (jeu `…_c2_20260316_EN_c`) devient
> la cohorte **de calibration** : les prompts s'y règlent. Ce ticket faisait de c2 le jeu de
> mesure hors échantillon ; ses mesures sur c2 (Jev 4,64 et 5,25, gemini-3.5 4,76, bande
> tabulaire [2,53 ; 3,71]) sont désormais des mesures sur le jeu de calibration. Le résultat
> hors échantillon de Jev s'obtient autrement : re-régler son prompt sur c2, le noter une fois
> sur c1, contre la bande c1 [3,60 ; 4,09]. L'article court porte `[re-tuning pending]` à cet
> endroit (tableau 1, §§ 5.1 et 5.3).

---

## 0. Ce qui existe déjà, et ce qui manque

Inventaire du 2026-09-22 dans `data/experiences/`.

| Mesure | Cohorte | Existe | Manque |
|---|---|---|---|
| gemini-3.5 × `prompt_expert_05`, graine 42 | c1 | ✓ 4,86 | |
| gemini-3.5 × `prompt_expert_05`, graines 123 et 789 | c1 | ✓ 4,65 et 4,30 | |
| gemini-3.5 × `prompt_minimal_02` | c1 | ✓ 7,02 | graines 123, 789 |
| jev × `prompt_expert_32` | c1 | ✓ 3,65 (en échantillon) | graines 123, 789 |
| jev × `prompt_expert_05` | c1 | ✓ | graines 123, 789 |
| jev × `prompt_minimal_02` | c1 | ✓ 13,75 | |
| Quatre références tabulaires, trois planchers | c1 | ✓ | |
| gemini-3.5 × `prompt_expert_05` | **c2** | déclaré le 22/09 à 13 h 42, **jamais exécuté** (`experience.yaml` seul) | exécution |
| tout le reste | **c2** | | tout |

La seconde cohorte et son jeu existent : `data/population/population_1000_AAMAS_v6_c2` et
`data/jeux/population_1000_AAMAS_v6_c2_20260316_EN_c`, sans un seul persona commun avec c1
(changelog du 2026-09-22). **Aucun prompt n'a été réglé sur c2 : tout ce qui s'y mesure est hors
échantillon, pour les deux modèles à la fois.** C'est ce qui rend le carré équitable sans
avoir à régler un prompt sur mesure pour gemini.

Le déterminisme de Jev est **inconnu** (ticket 096, § « Graine / température : non
documentées »). Les rejeux à graines le mesurent en passant.

Les rejeux à graines existants font varier `graine_ordre`, `graine_tirage` et `calendrier.graine`
ensemble (`go123_gt123_gc123`, `go789_gt789_gc789`). Ce ticket garde cette convention : une
graine = les trois à la même valeur.

---

## 1. Lot A — le carré hors échantillon sur c2

Douze expériences, graine 42, mode `sans_simulateur`, mémoire désactivée, contrainte de chaîne
et verrou retour actifs, comme sur c1. Chacune dérive (`derive_de`) de son homologue c1 en ne
changeant que `population.chemin` et `jeu.nom`. La déclaration existante du run gemini c2 sert
de gabarit ; elle est correcte et n'a qu'à être exécutée.

| # | Décideur | Prompt | Nom attendu |
|---|---|---|---|
| A1 | gemini-3.5-flash-lite | `prompt_minimal_02` | `exp_gemini-35-fl_promin02_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_t0_nosim` |
| A2 | gemini-3.5-flash-lite | `prompt_expert_05` | `exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c_t0_nosim` (déjà déclaré) |
| A3 | gemini-3.5-flash-lite | `prompt_expert_32` | `exp_gemini-35-fl_proexp32_…_c2_…` |
| A4 | jev-1.13.0 | `prompt_minimal_02` | `exp_jev-1130_promin02_…_c2_…_nosim` |
| A5 | jev-1.13.0 | `prompt_expert_05` | `exp_jev-1130_proexp05_…_c2_…_nosim` |
| A6 | jev-1.13.0 | `prompt_expert_32` | `exp_jev-1130_proexp32_…_c2_…_nosim` |
| A7–A10 | logit multinomial, gradient boosté, régression à noyau, forêt aléatoire | | `exp_{mnl,lgbm,klr,rf}_…_c2_…_nosim` |
| A11–A13 | hasard uniforme, tout-voiture, durée minimale | | planchers sur c2 |

A3 est la ligne qui rend le carré carré : le prompt réglé pour Jev, servi à gemini. Sans elle
on ne sait pas si l'avantage de `prompt_expert_32` sur c1 tient au texte ou au modèle qui le lit.

A7 à A13 sont déterministes et gratuits ; ils donnent le plafond et le plancher **de c2**, sans
lesquels aucune ligne de A1 à A6 ne se lit. Ne pas comparer un score c2 à un plafond c1.

**Scorage.** Chaque exécution reçoit son `scores.json` par le scoreur habituel, formule
`v1_reference`, référentiel EMC² 2023 inchangé. Puis les différences appariées de l'annexe H.1
se recalculent sur c2 avec le script existant (`docs/traces/2026-09-21_ticket096_lot2/paired_avec_jev.py`,
2 000 réplicats, rééchantillonnage par grappe au niveau de la personne), pour les quatorze paires
A1–A6 × A7–A10.

---

## 2. Lot B — trois graines par décideur clé, sur c1

Six exécutions, graines 123 et 789, dérivées des runs graine 42 correspondants.

| # | Décideur | Prompt | Graines à ajouter |
|---|---|---|---|
| B1–B2 | jev-1.13.0 | `prompt_expert_32` | 123, 789 |
| B3–B4 | jev-1.13.0 | `prompt_expert_05` | 123, 789 |
| B5–B6 | gemini-3.5-flash-lite | `prompt_minimal_02` | 123, 789 |

gemini-3.5 × `prompt_expert_05` a déjà ses trois graines : 4,86 / 4,65 / 4,30, soit une
étendue de 0,56 point, sous la résolution de cohorte de ±1,3. **C'est la première mesure de
dispersion inter-graines du corpus, et elle n'est écrite nulle part dans l'article.** Le lot B
la complète, il ne l'inaugure pas.

Si Jev rend un score identique au centième sur les trois graines, il est déterministe à
température nulle et le ticket 096 se met à jour d'une ligne. S'il varie, sa dispersion se
publie comme celle des autres.

---

## 3. Lot C — conditionnel : un prompt sur mesure pour gemini, en échantillon

**À ne lancer que si le lot A donne le scénario 3 du § 5**, et si l'auteur veut alors
séparer « c'est le modèle » de « c'est le prompt ». Réglage de `prompt_expert_NN` contre les
écarts par strate de gemini-3.5 lus sur c1, par la procédure du § 5.2.2 (mutations
successives, audit `prompt-auditor` avant chaque lancement, six textes au plus), puis mesure
sur c1 et sur c2. C'est du temps humain, pas du temps machine : de l'ordre de six lancements
et d'une demi-journée.

---

## 4. Contraintes d'exécution

- **Une seule campagne à la fois**, et jamais pendant un run manuel : une campagne recrée le
  controller et tue un run en cours (règle du 2026-09-16, mémoire du dépôt). Vérifier
  `experiments/current/` et `campagnes/*/etat.json` avant de déclarer.
- La campagne se déclare dans `campagnes/<nom>.yaml` selon le § 6 sexies de
  `docs/arch/plateforme-experiences.md`. Trois phases suffisent : A7–A13 d'abord (déterministes,
  ils donnent l'échelle), puis A1–A6, puis B1–B6.
- Chaque `experience.yaml` porte `derive_de` vers son homologue c1 ou graine 42 : la parenté
  doit être lisible dans le dossier, pas reconstruite.
- Journaliser en fin de campagne : nombre d'expériences lancées, scorées, refusées, durée
  totale, et une ligne par score. Un `[ALARME]` si une exécution rend moins de 3 000 décisions
  scorées sur les 3 299 attendues (c1 en rend 3 154 ; c2 doit rendre un compte du même ordre,
  à établir au premier run déterministe).
- Aucun chiffre de ce ticket n'entre dans `docs/paper/article/` sans accord : verrou.

---

## 5. Critères d'acceptation, écrits avant la mesure

Le ticket est **terminé** quand les dix-neuf exécutions des lots A et B ont un `scores.json`,
que les différences appariées c2 sont calculées, et que le tableau ci-dessous est rempli dans
`docs/traces/<date>_ticket103/README.md`. L'issue se lit sur trois questions.

**Q1 — Jev tient-il hors échantillon ?** Composite de A6 (jev × expert_32, c2) contre la
bande [min ; max] de A7–A10, et différence appariée à chacune des quatre.
- *Scénario 1 :* A6 dans la bande, aucune paire ne l'en sépare (intervalle contenant zéro
  face à au moins deux références). **La thèse est hors échantillon.** Le plan s'écrit tel quel.
- *Scénario 2 :* A6 à moins de 1,3 point au-dessus de la bande. Jev se publie comme
  **borne supérieure atteinte hors échantillon**, la thèse tient (« la délibération n'améliore
  pas », pas « Jev gagne »). Le § 5.3 du plan perd son titre affirmatif.
- *Scénario 3 :* A6 à plus de 1,3 point au-dessus. Le résultat c1 était un effet d'échantillon.
  Le § 5.3 du plan devient une phrase, C2 se replie sur ses trois autres constats, le lot C
  s'ouvre si l'auteur le veut.

**Q2 — Le carré est-il carré ?** A3 (gemini × expert_32) contre A2 (gemini × expert_05), et
A6 contre A5. Si `prompt_expert_32` améliore gemini autant qu'il améliore Jev, l'effet est le
texte ; s'il n'améliore que Jev, l'effet est le couple. La phrase du § 5.3 du plan se choisit
selon la réponse, et pas avant.

**Q3 — Les écarts survivent-ils aux graines ?** Pour chaque paire de décideurs que le § 5 du
plan compare, le signe de la différence doit être le même sur les trois graines. Une paire dont
le signe change sur une graine **ne se publie pas comme un écart**, quelle que soit sa taille
sur la graine 42. L'étendue inter-graines de chaque décideur se publie dans le tableau de
l'échelle, en colonne, à côté du composite.

**Aucun de ces trois critères ne se réécrit après lecture des scores.** Si un cas non prévu se
présente, il s'ajoute au README de trace avec sa date, et la règle ci-dessus reste celle qui
compte.

---

## 6. Ce que ce ticket ne fait pas

- Il ne mesure pas les décideurs sur le jeu d'audit unitaire (`pop-enquete_058_test`) sur c2 :
  l'audit porte sur les journées déclarées de l'enquête, il n'a pas de « c2 ».
- Il ne rejoue pas le chapitre 7 (choc, presse) : autre substrat, autre ticket (064, 095).
- Il ne touche pas au texte de l'article.

## 7. Dépendances

- **Dépend de :** aucun ticket. Toutes les entrées existent.
- **Bloque :** la version définitive de `docs/paper/article-court/PLAN.md` (§ 5.3 et § 7),
  et toute réécriture des chapitres 6, 8 et 9 de l'article.
- **Voisin :** ticket 101 (intégration de Jev dans l'article), dont les lots 2 à 6 n'ont pas à
  attendre ce ticket pour les phrases qui ne citent pas le 3,65.
