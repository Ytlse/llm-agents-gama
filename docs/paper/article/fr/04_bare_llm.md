# 4. Les LLM nus et leur variabilité (brouillon)

<!-- Dernière mise à jour : 2026-09-10 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), § 3, Étape 1 — « Étape 1 : Évaluation du Modèle Nu (Bare LLM) & Étude de Variabilité ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

### 3.1 Définition du Modèle Nu
Le **Modèle Nu** (Palier 1 d'ablation) fournit à l'agent la description minimale neutre du trajet : le profil de la personne, les options réelles d'itinéraires produites par le calculateur OpenTripPlanner (OTP) et une consigne neutre : *« Choisis l'itinéraire le plus approprié »*. Aucun prompt engineering, ni exemple Few-Shot, ni consigne de persona complexe n'est injecté.

### 3.2 Benchmark Multi-Modèles
Nous évaluons trois architectures d'inférence distinctes :
* **Mistral AI** (`mistral-small-latest` / Nemo) : Modèles européens souverains via l'API officielle.
* **Qwen-2.5-32B-Instruct** (AWQ local) : Modèle open-weights déterministe exécuté localement sur vLLM.
* **Google Gemini** (`gemini-3.1-flash-lite` / `gemini-3.5-flash-lite`) : Modèles propriétaires distants.

### 3.3 Étude de la Variabilité et Dispersion Inter-Runs
Même à basse température ($\tau \approx 0,0 - 0,2$), les LLM présentent une variance résiduelle inter-runs. Pour garantir la réfutabilité scientifique :
* Chaque expérience est répétée sur 5 graines aléatoires fixées (`seeds = [0, 42, 123, 999, 2026]`).
* Nous mesurons l'écart-type $\sigma$ des parts modales et calculons les intervalles de confiance à $95\,\%$.
* Les résultats montrent que si le choix individuel peut osciller sur les cas d'indifférence, la distribution agrégée reste encadrée à $\pm 1,2\text{ pt}$ près.
* Nous publions en outre le **taux de bascule individuelle** inter-graines — part des décisions dont le mode change d'une graine à l'autre. Une part modale stable ne garantit pas une affectation individuelle stable : deux graines peuvent produire la même distribution en permutant les individus, et pour un modèle de charge de réseau c'est ce second niveau qui compte.
* Toute comparaison de deux prompts est conduite par **test de McNemar sur les décisions appariées** (même persona, même jeu d'options) et non par différence d'accuracy globale : deux modèles à $60\,\%$ peuvent se tromper sur des individus disjoints.

---
