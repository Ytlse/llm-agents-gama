# 8. Conclusion (brouillon)

<!-- Dernière mise à jour : 2026-09-10 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), § 7, Conclusion & Enseignements — « Conclusion & Enseignements ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

1. **Pas de LLM pour la prédiction de masse statique (Plafond de Tier 3)** : En accord direct avec les résultats du benchmark SILICA (*Bin Tareaf et al., 2026*), les agents LLM échouent à reproduire fidèlement la distribution empirique de mobilité humaine sans calage statistique lourd. Les arbres supervisés (LightGBM) sont $\approx 2\,700\times$ plus rapides (moins d'une seconde contre $\approx 45$ minutes pour $10\,000$ trajets), gratuits en tokens et quatre fois plus fidèles en argmax ($7,30\text{ pt}$ vs $29,81\text{ pt}$ d'erreur L1).
2. **La valeur du LLM réside dans la dépendance contextuelle et l'adaptation (Validité de Tier 2)** : Conformément à la thèse de Baronchelli (*Baronchelli, 2026*), l'intérêt des LLMs ne réside pas dans leur statut de « proxy humain statistique », mais dans leur comportement adaptatif émergent : dépendance non tabulée (presse locale, dégoût, densité de foule, agrément) et non indépendante (hystérésis $J+1$ avec mémoire court-terme $\mathcal{M}_t$, arbitrage intra-ménage, chaîne spatiale des véhicules). Partout ailleurs, un modèle tabulaire fait mieux et moins cher.
3. **Un enseignement de mesure, transférable hors de ce cas** : Une variante à $93,4\,\%$ d'accuracy sur l'enquête a produit le **pire** score en simulation ($9,28$ contre $7,40$ de composite), la distance reconstruite depuis la durée déclarée contenant le mode retenu. Toute évaluation d'agent génératif doit être notée **là où le modèle sert**, pas là où il est facile de le noter.
4. **L'architecture hybride en cascade répond à la dichotomie fondamentale** : Réconcilier les deux questions de Baronchelli par une division du travail — confier $90\,\%$ du flux nominal au calage statistique supervisé (Tier 3), et réserver le raisonnement génératif LLM aux $10\,\%$ de situations complexes, perturbations et ruptures contextuelles (Tier 2).

---
