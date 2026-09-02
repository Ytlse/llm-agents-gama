# Instructions de Versionnement pour les Agents AI (Claude & Antigravity)

> **Important pour les assistants IA (Claude, Antigravity) :**  
> Tous les fichiers situés dans le dossier `docs/paper/` (ainsi que dans ses sous-dossiers `actualites/`, `archive/`, etc.) font partie intégrante de la chaîne d'écriture et de documentation scientifique du projet. **Chaque fichier créé, modifié ou restructuré doit obligatoirement être versionné.**

---

## 1. Règles de Versionnement et d'Archivage

1. **Historique & Numérotation de Version dans les Fichiers :**
   - Tout document principal (`MANUSCRIT_DETAILLE_2026.md`, `MANUSCRIT_DETAILLE_2026_SLIDES.html`, etc.) doit indiquer explicitement son numéro de version (ex: `v1.0`, `v1.1`, `v1.2`, `v1.3`, ...) et sa date de mise à jour dans l'en-tête et l'historique des versions.
   - Les incréments de version suivent la convention :
     - `v1.x` : Révisions mineures (ajouts de sections, précisions techniques, réalignement de la démarche expérimentale, mise à jour de graphiques ou données).
     - `v2.0` : Refonte majeure du plan, modification d'hypothèses centrales ou soumission à revue.


2. **Archivage des Versions Majeures/Intermédiaires (`docs/paper/archive/`) :**
   - Lorsqu'une version franchit une étape importante (ex: passage de `v1.2` à `v1.3`), une copie figée de la version antérieure doit être conservée dans le dossier `archive/` (ex: `archive/MANUSCRIT_DETAILLE_2026_v1.2.md`).
   - Ne jamais supprimer ni écraser destructivement les fichiers archivés.

3. **Suivi Git (Version Control) Obligatoire :**
   - Tout nouveau fichier créé (`.md`, `.html`, `.py`, `.json`, `.png`) doit immédiatement être ajouté à l'index Git (`git add <fichier>`).
   - Les commits doivent comporter un message explicite décrivant les modifications apportées aux manuscrits et slides.

4. **Alignement Synchronisé Markdown $\leftrightarrow$ HTML :**
   - `MANUSCRIT_DETAILLE_2026.md` est le document maître (source de vérité textuelle et théorique).
   - `MANUSCRIT_DETAILLE_2026_SLIDES.html` est le document interactif de présentation des slides.
   - **Toute modification de fond dans `MANUSCRIT_DETAILLE_2026.md` doit être immédiatement et obligatoirement répercutée dans `MANUSCRIT_DETAILLE_2026_SLIDES.html`** pour maintenir une parité parfaite entre les deux supports.

5. **Chiffre publié = chiffre recoupé.**
   - Tout chiffre entrant dans un document de `docs/paper/` est recalculé depuis sa source dans le dépôt — `scripts/progedo_logit/mode_choice_policy_metrics.json` (accuracy, LogLoss, matrice de confusion, importances), `scripts/progedo_logit/feature_spec.json` (contrat de variables), `docs/arch/score-synthesis.md` (renormalisation sur l'offre, témoin d'effectif), `docs/changelog.md` (temps terminaux, variantes mesurées) — et non recopié d'une version antérieure d'un manuscrit.
   - Les écarts constatés lors d'un recoupement sont consignés dans le **journal des corrections** (Annexe F de `MANUSCRIT_DETAILLE_2026.md`), jamais corrigés en silence.

---

## 2. Inventaire des Fichiers du Dossier `paper/`

| Fichier / Dossier | Rôle & Contenu | Statut de Versionnement |
|---|---|---|
| [`MANUSCRIT_DETAILLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/MANUSCRIT_DETAILLE_2026.md) | Document scientifique maître (Version courante `v1.4`). | **Versionné & Suivi Git** |
| [`MANUSCRIT_DETAILLE_2026_SLIDES.html`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/MANUSCRIT_DETAILLE_2026_SLIDES.html) | Présentation HTML interactive (mode slides & doc). | **Versionné & Suivi Git** |
| [`PLAN_ARTICLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PLAN_ARTICLE_2026.md) | Trame stratégique de la publication (Version courante `v1.4`, démarche 0 ➔ 1 ➔ 2 ➔ 3a ➔ 3b ➔ Perspectives). | **Versionné & Suivi Git** |
| [`PROTOCOLE_SCIENTIFIQUE.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PROTOCOLE_SCIENTIFIQUE.md) | Hypothèses de recherche et formalisation mathématique (Version courante `v1.3`). | **Versionné & Suivi Git** |
| [`SLIDES_SEMINAIRE_2026.html`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/SLIDES_SEMINAIRE_2026.html) | Support de séminaire 40–45 min (Version courante `v1.1`, 31 planches à la forme d'un article : abstract, sections numérotées, figures et tables légendées). Modes diaporama et document, notes de planche sur la touche `n`. Publié en Artifact : https://claude.ai/code/artifact/1a292f80-16df-4bcf-baea-59a5947490b1 | **Versionné & Suivi Git** |
| [`RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md) | Rapport sur les scénarios d'actualité et cas de test toulousains. | **Versionné & Suivi Git** |
| [`INSTRUCTIONS_SOUMISSION_AAMAS.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/INSTRUCTIONS_SOUMISSION_AAMAS.md) | Directives et consignes de soumission AAMAS 2027 (OpenReview, format, matériel supplémentaire, règles IA). | **Versionné & Suivi Git** |
| [`quotas_summary.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/quotas_summary.md) | Synthèse technique des quotas API, SWRR et fournisseurs LLM. | **Versionné & Suivi Git** |
| [`quotas_summary.html`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/quotas_summary.html) | Interface HTML interactive récapitulative des quotas. | **Versionné & Suivi Git** |
| `actualites/` | Corpus d'articles de presse locale toulousaine sourcés pour la validité écologique. | **Versionné & Suivi Git** |
| `archive/` | Historique des versions antérieures (`v1.0`, `v1.1`, `v1.2`, etc.), y compris les supports HTML figés. | **Versionné & Suivi Git** |
